# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, formatLang


class PosMakePayment(models.TransientModel):
    _inherit = 'pos.make.payment'

    use_customer_credit = fields.Boolean(
        default=True, string='Use Customer Credit'
    )
    currency_id = fields.Many2one(related='config_id.currency_id')
    customer_credit_balance = fields.Monetary(
        compute='_compute_customer_credit_balance', currency_field='currency_id'
    )

    def _get_order(self):
        return self.env['pos.order'].browse(self.env.context.get('active_id', False))

    def _compute_customer_credit_balance(self):
        order = self._get_order()
        for wizard in self:
            wizard.customer_credit_balance = (
                order.partner_id.pos_credit_balance if order.partner_id else 0.0
            )

    def _credit_discounted_amount(self, order, base_amount):
        """``base_amount`` minus whatever of the partner's banked credit
        would actually apply, capped at both the available balance and the
        order's own residual -- shared by ``default_get`` (initial suggestion)
        and the ``use_customer_credit`` onchange (live toggle), so the
        displayed ``amount`` always matches the checkbox's current state.
        """
        if not self.use_customer_credit or not order or not order.partner_id:
            return base_amount
        balance = order.partner_id.pos_credit_balance
        if balance <= 0:
            return base_amount
        residual = order.currency_id.round(order.amount_total - order.amount_paid)
        applied = min(balance, residual)
        return max(order.currency_id.round(base_amount - applied), 0.0)

    @api.model
    def default_get(self, fields_list):
        """Only adjusts the *suggested* ``amount`` shown on the form -- no
        persistent write happens here (a wizard's ``default_get`` can be
        called speculatively/without ever being confirmed, so applying the
        credit for real has to wait for ``check()``).
        """
        res = super().default_get(fields_list)
        if 'amount' not in fields_list:
            return res
        order = self._get_order()
        # `self.use_customer_credit` isn't set yet at this point (the record
        # doesn't exist) -- `new()` a throwaway with the field's own default
        # (True) unless the caller is pre-seeding it via context/res.
        wizard = self.new({'use_customer_credit': res.get('use_customer_credit', True)})
        res['amount'] = wizard._credit_discounted_amount(order, res.get('amount', 0.0))
        return res

    @api.onchange('use_customer_credit')
    def _onchange_use_customer_credit(self):
        order = self._get_order()
        if not order:
            return
        residual = order.currency_id.round(order.amount_total - order.amount_paid)
        self.amount = self._credit_discounted_amount(order, residual)

    def _apply_customer_credit(self, order):
        """Wizard-level opt-in check; the actual consumption logic is shared
        with the POS frontend touch checkout on ``pos.order`` itself (see
        ``apply_customer_credit`` there), since both need the exact same
        behavior.
        """
        self.ensure_one()
        if not self.use_customer_credit:
            return
        order.apply_customer_credit()

    def check(self):
        """Reuse the core "Payment" wizard to collect the remaining balance
        of a ``partially_paid`` order.

        Core's ``check()`` only does something useful when
        ``order.state == 'draft'``: it registers the payment, and if the
        order then becomes fully paid it processes/closes it, otherwise it
        silently reopens the very same wizard. For a ``partially_paid``
        order the state is never ``'draft'`` again, so core's branch is a
        dead end.

        For that case we register the payment exactly like core does, then
        always call ``_process_saved_order(False)`` -- regardless of
        whether the order is now fully covered or not -- and let our
        ``pos.order`` override decide whether the result is ``paid`` or
        stays ``partially_paid``. We then close the wizard with a
        notification describing the outcome instead of reopening it.
        """
        self.ensure_one()

        order = self._get_order()
        self._apply_customer_credit(order)

        if order.state != 'partially_paid':
            return super().check()

        if self.payment_method_id.split_transactions and not order.partner_id:
            raise UserError(_(
                "Customer is required for %s payment method.",
                self.payment_method_id.name,
            ))

        currency = order.currency_id

        init_data = self.read()[0]
        payment_method = self.env['pos.payment.method'].browse(init_data['payment_method_id'][0])
        # Duck-typed extension point from l10n_latam_check_ext (if installed):
        # this module has no business knowing about AR check payments, but
        # must still not silently drop that module's fields/validation when
        # both are installed together (see l10n_latam_check_ext's
        # models/pos_make_payment.py for why this exists -- its own check()
        # never runs for a 'partially_paid' order, since this override
        # returns before ever calling super()).
        validate = getattr(self, '_l10n_latam_check_validate', None)
        if validate:
            validate(payment_method)
        if not float_is_zero(init_data['amount'], precision_rounding=currency.rounding):
            payment_vals = {
                'pos_order_id': order.id,
                'amount': order._get_rounded_amount(
                    init_data['amount'],
                    payment_method.is_cash_count or not self.config_id.only_round_cash_method,
                ),
                'name': init_data['payment_name'],
                'payment_method_id': init_data['payment_method_id'][0],
            }
            extra_vals = getattr(self, '_l10n_latam_check_payment_vals', None)
            if extra_vals:
                payment_vals.update(extra_vals(payment_method))
            order.add_payment(payment_vals)

        # `_send_order` is a session/frontend hook (a no-op in core, only
        # overridden by the online-ordering preparation-display module,
        # which is not installed here) and `notify_synchronisation` targets
        # a live POS session's frontend; neither applies to a plain backend
        # payment registration on an order that may well belong to an
        # already-closed session, so unlike core's `check()` we don't call
        # them here.
        order._process_saved_order(False)

        if order.state == 'paid':
            message = _("Order %s is now fully paid.", order.name)
            notification_type = 'success'
        else:
            remaining = order.amount_total - order.amount_paid
            message = _(
                "Partial payment registered on order %(name)s. Remaining balance due: %(amount)s.",
                name=order.name,
                amount=formatLang(self.env, remaining, currency_obj=currency),
            )
            notification_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Payment registered"),
                'message': message,
                'type': notification_type,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
