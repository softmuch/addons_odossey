# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, formatLang


class PosMakePayment(models.TransientModel):
    _inherit = 'pos.make.payment'

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

        order = self.env['pos.order'].browse(self.env.context.get('active_id', False))

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
        if not float_is_zero(init_data['amount'], precision_rounding=currency.rounding):
            order.add_payment({
                'pos_order_id': order.id,
                'amount': order._get_rounded_amount(
                    init_data['amount'],
                    payment_method.is_cash_count or not self.config_id.only_round_cash_method,
                ),
                'name': init_data['payment_name'],
                'payment_method_id': init_data['payment_method_id'][0],
            })

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
