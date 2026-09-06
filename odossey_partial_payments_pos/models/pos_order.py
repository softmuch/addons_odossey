# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_round

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # `ondelete='set default'` (-> 'draft') is used instead of the more
    # destructive 'cascade' so that, if this module is ever uninstalled,
    # orders left in 'partially_paid' are simply reset to 'draft' instead of
    # being deleted outright (deleting real pos.order records on uninstall
    # would be unacceptable for a client database).
    # Anchored on 'cancel' (not just appended) so it lands right after
    # 'draft' in the selection's real order -- `statusbar_visible` in the
    # view only filters which states show, it does NOT reorder them; the
    # widget always follows this field's own selection order.
    state = fields.Selection(
        selection_add=[('partially_paid', 'Partially Paid'), ('cancel',)],
        ondelete={'partially_paid': 'set default'},
    )
    # Persisted (not just a wizard-transient flag) so the POS frontend touch
    # checkout -- which never goes through `pos.make.payment` -- can drive
    # the same opt-in/opt-out choice via its own checkbox, synced like any
    # other order field. `pos.make.payment` keeps its own separate
    # `use_customer_credit` field for the backend-wizard flow; both end up
    # calling the same `apply_customer_credit()` below.
    use_customer_credit = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Don't trust an incoming ``state: 'paid'`` at creation time.

        The POS frontend optimistically sets ``order.state = "paid"``
        locally as soon as the cashier hits Validate/Partial Payment,
        *before* syncing (see ``finalizeValidation`` in
        ``order_payment_validation.js``), and for a brand-new order (no
        prior draft/parked ``pos.order`` record) core's ``_process_order``
        creates the record directly with that ``state`` baked into
        ``vals`` -- unlike its handling of an *existing* order being
        re-synced, where it resets ``state`` back to the record's current
        DB value first and lets ``_process_saved_order`` decide.

        Without this, a genuinely partial payment would get created as
        ``state == 'paid'`` and then our ``action_pos_order_paid`` (called
        right after, from ``_process_saved_order``) would try to correct it
        to ``partially_paid`` -- which core's own ``write()`` guard forbids
        once a record has ever been 'paid'/'done'/'invoiced'
        ("This order has already been paid...").

        So: force it back to 'draft' at creation and let
        ``action_pos_order_paid`` (called immediately afterwards in the
        same request) decide the real final state, exactly like core
        already does for the existing-order/re-sync path. A genuinely
        fully-paid order ends up 'paid' either way -- this only changes
        *when* that state is assigned, not the end result.
        """
        for vals in vals_list:
            if vals.get('state') == 'paid':
                vals['state'] = 'draft'
        return super().create(vals_list)

    def write(self, vals):
        """Give a partially paid order its real name, instead of leaving it
        as '/' like a draft.

        Core only assigns the sequence-based name when a write sets
        ``state`` to ``'paid'`` (see ``write()`` in core's
        ``pos_order.py``). Since a partial payment now ends in
        ``'partially_paid'`` instead, that condition never matched and the
        order stayed named '/' indefinitely. Mirror the same logic for our
        new state.

        Also handles a backend-reopened order (see odoxeus_rioseed, which
        relaxes the `lines`/`payment_ids` readonly for 'paid'/'done' orders):
        core's own write(), called via super() below, would otherwise (a)
        refuse to move a 'paid'/'done' order to anything outside
        ('paid', 'done', 'invoiced') -- the "This order has already been
        paid" guard -- and (b) raise "The paid amount is different from the
        total amount of the order" once the edited lines/payments no longer
        match. We sidestep both by writing `state` through the base ORM
        directly (bypassing every model-level write() override, core's
        included) *before* the real field write, so that by the time core's
        write() runs, the order is already 'partially_paid' and neither
        guard fires (both are conditioned on state in ('paid', 'done')).
        """
        orders_to_reconcile = self.browse()
        if vals.get('lines') or vals.get('payment_ids'):
            orders_to_reconcile = self.filtered(
                lambda o: o.state in ('paid', 'done') and o.nb_print == 0
            )
            if orders_to_reconcile:
                models.Model.write(orders_to_reconcile, {'state': 'partially_paid'})

        if vals.get('state') == 'partially_paid':
            for order in self:
                if order.name == '/':
                    session = (
                        self.env['pos.session'].browse(vals['session_id'])
                        if not order.session_id and vals.get('session_id')
                        else False
                    )
                    vals['name'] = order._compute_order_name(session)

        res = super().write(vals)

        if orders_to_reconcile:
            orders_to_reconcile._compute_prices()
            for order in orders_to_reconcile:
                if order._is_order_paid_with_rounding():
                    order.write({'state': 'paid'})

        return res

    def _is_order_paid_with_rounding(self):
        """Re-derive core's ``isPaid`` boolean from ``action_pos_order_paid``
        (amount comparison + cash-rounding tolerance), WITHOUT calling it.

        We used to let core raise its "Order %s is not fully paid." error
        and catch it by comparing ``str(error)`` against a pre-translated
        copy of that same message. That broke in practice: depending on
        timing/context the two translations don't reliably compare equal
        (and, more fundamentally, string-matching a translatable error
        message is just the wrong tool for this). Recomputing the exact
        same boolean core uses avoids the whole class of problem: no
        exception is raised (and none needs to be caught) on the partial
        payment path at all.

        NOTE: this duplicates core's formula on purpose, see
        ``action_pos_order_paid`` in ``point_of_sale/models/pos_order.py``.
        If core ever changes that formula, this needs to be updated to
        match, or the two can silently disagree about edge cases (e.g. a
        cash-rounding difference just inside/outside the tolerance).
        """
        self.ensure_one()

        if not self.config_id.cash_rounding \
           or self.config_id.only_round_cash_method \
           and not any(p.payment_method_id.is_cash_count for p in self.payment_ids):
            total = self.amount_total
        else:
            total = float_round(
                self.amount_total,
                precision_rounding=self.config_id.rounding_method.rounding,
                rounding_method=self.config_id.rounding_method.rounding_method,
            )

        is_paid = float_is_zero(total - self.amount_paid, precision_rounding=self.currency_id.rounding)

        if not is_paid and self.config_id.cash_rounding:
            currency = self.currency_id
            if self.config_id.rounding_method.rounding_method == "HALF-UP":
                max_diff = currency.round(self.config_id.rounding_method.rounding / 2)
            else:
                max_diff = currency.round(self.config_id.rounding_method.rounding)
            diff = currency.round(self.amount_total - self.amount_paid)
            is_paid = abs(diff) <= max_diff

        return is_paid

    def action_pos_order_set_draft(self):
        """Send a partially paid order back to draft so it can be edited
        (e.g. add lines) and re-confirmed, reusing the existing partial
        payment "Payment" button to collect the (possibly larger) balance.

        Restricted to ``partially_paid``: a fully ``paid``/``done`` order
        already has its stock picking and/or invoice generated (see
        ``_process_saved_order`` below), so reverting it to draft would
        leave those inconsistent with the order. A ``partially_paid``
        order never reached that point, so there is nothing to undo.
        """
        if any(order.state != 'partially_paid' for order in self):
            raise UserError(_("Only a partially paid order can be sent back to draft."))
        self.write({'state': 'draft'})

    def action_pos_order_paid(self):
        """Allow an order to be saved/finalized when it is only partially paid.

        - Fully paid (per ``_is_order_paid_with_rounding``, same formula
          core uses) -> behave exactly like core: ``super()`` ends in
          ``state == 'paid'``.
        - Nothing at all was paid (``amount_paid`` is zero) -> that's not a
          "partial payment", it's "no payment": call ``super()`` too and let
          core raise its usual error unchanged.
        - Some money came in but not enough to cover the total -> deliberate
          partial payment: flag the order as ``partially_paid`` instead of
          blocking the save (stock/invoicing are left untouched, see our
          override of ``_process_saved_order`` below). No exception is
          raised or caught on this path.
        """
        self.ensure_one()

        if self._is_order_paid_with_rounding() or float_is_zero(
            self.amount_paid, precision_rounding=self.currency_id.rounding
        ):
            return super().action_pos_order_paid()

        self.write({'state': 'partially_paid'})
        return True

    def apply_customer_credit(self):
        """Consume up to this order's own residual from `self.partner_id`'s
        banked `pos.customer.credit` balance, booked as its own "Crédito
        Cliente" payment line. Shared by the backend `pos.make.payment`
        wizard (see its own `_apply_customer_credit`, gated by the wizard's
        transient field) and the POS frontend touch checkout below (gated
        by this order's own persisted `use_customer_credit` field).

        Never applies more than the order's own residual -- this alone must
        never overpay the order; whatever else gets tendered can still
        overpay it, and that's handled by `_redistribute_overpayment` as
        usual.
        """
        self.ensure_one()
        if not self.partner_id:
            return
        balance = self.partner_id.pos_credit_balance
        if balance <= 0:
            return
        residual = self.currency_id.round(self.amount_total - self.amount_paid)
        if residual <= 0:
            return
        applied = min(balance, residual)
        credit_method = self.env['pos.payment.method']._get_or_create_credit_payment_method(
            self.company_id
        )
        self.sudo().add_payment({
            'pos_order_id': self.id,
            'amount': applied,
            'payment_method_id': credit_method.id,
        })
        self.env['pos.customer.credit'].sudo().create({
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'amount': -applied,
            'used_order_id': self.id,
        })

    def _redistribute_overpayment(self):
        """When this order ends up paid IN EXCESS (payments sum above its
        own total), first shift the extra money to this same customer's
        other ``partially_paid`` orders (oldest first), and bank whatever's
        left as reusable credit (``pos.customer.credit``) once none remain.

        All the actual money movement between orders is booked through a
        dedicated, journal-less "Crédito Cliente" tender
        (``pos.payment.method.is_credit_transfer``) rather than the real
        payment method that caused the excess: preserving the original
        tender on a cross-order/cross-session transfer would require it to
        also be configured on whatever session the target order belongs to
        (``pos.payment._check_payment_method_id``), which isn't guaranteed
        and isn't the point here -- this is pure internal bookkeeping, not a
        new real payment. Nothing here creates any *new* real money: the
        negative correction line on `self` and the positive line(s) on the
        target order(s) always sum to zero, so a session's own cash-close
        totals are unaffected when both orders share a session, and are
        correctly shifted between sessions when they don't (the excess
        really did arrive in whichever session collected it, and is now
        credited to a sale rung up in another one).
        """
        self.ensure_one()
        excess = self.currency_id.round(self.amount_paid - self.amount_total)
        if excess <= 0 or self.currency_id.is_zero(excess):
            return
        if not self.partner_id:
            # Nothing sensible to redistribute or bank an anonymous
            # overpayment against -- leave it as an unexplained excess on
            # this order rather than silently discarding it.
            return

        credit_method = self.env['pos.payment.method']._get_or_create_credit_payment_method(
            self.company_id
        )
        remaining = excess
        # `pos.payment.create()` alone never updates `amount_paid` -- that
        # field isn't an automatic compute, it's a plain stored value only
        # ever kept in sync by whoever creates the payment (see
        # `pos.order.add_payment`, which does exactly `create()` then
        # `self.amount_paid = self._compute_amount_paid()`). Reuse it here
        # instead of a raw `create()` so this doesn't drift out of sync.
        self.sudo().add_payment({
            'pos_order_id': self.id,
            'amount': -remaining,
            'payment_method_id': credit_method.id,
        })

        targets = self.env['pos.order'].sudo().search([
            ('partner_id', '=', self.partner_id.id),
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'partially_paid'),
            ('id', '!=', self.id),
        ], order='date_order asc, id asc')
        for target in targets:
            if remaining <= 0:
                break
            residual = target.currency_id.round(target.amount_total - target.amount_paid)
            if residual <= 0:
                continue
            applied = min(remaining, residual)
            target.sudo().add_payment({
                'pos_order_id': target.id,
                'amount': applied,
                'payment_method_id': credit_method.id,
            })
            target._process_saved_order(False)
            remaining = self.currency_id.round(remaining - applied)

        if remaining > 0:
            self.env['pos.customer.credit'].sudo().create({
                'partner_id': self.partner_id.id,
                'company_id': self.company_id.id,
                'amount': remaining,
                'origin_order_id': self.id,
            })

    def _process_saved_order(self, draft):
        """Same as core, except stock pickings / cost computation are only
        triggered once the order actually reaches the 'paid' state.

        Core's ``_create_order_picking`` is not itself gated on
        ``state == 'paid'`` (it only checks ``self.picking_ids`` and
        ``_should_create_picking_real_time``), so without this guard a
        partially paid order finalized through ``action_pos_order_paid``
        above would still ship stock and compute margins as if it were
        fully paid. The invoicing block below is left untouched: it already
        checks ``self.state == 'paid'`` on its own.
        """
        self.ensure_one()
        if not draft and self.state != 'cancel':
            # Applying banked credit first (not just redistributing excess
            # after the fact) lets it cover part or all of THIS order too --
            # not only ones it's already overpaid -- exactly like the
            # backend wizard's own ordering (`_apply_customer_credit` before
            # its own payment branch).
            if self.use_customer_credit:
                self.apply_customer_credit()
            # Must run BEFORE `action_pos_order_paid`: `_is_order_paid_with_
            # rounding` is a near-EQUALITY check (`total - amount_paid` is
            # ~zero), not a `>=` one -- an overpaid order (`amount_paid`
            # above `amount_total`) fails it and falls through to
            # 'partially_paid' same as a genuine underpayment, unless the
            # excess is already netted out of `amount_paid` by the time this
            # runs.
            self._redistribute_overpayment()
            self.action_pos_order_paid()
            if self.state == 'paid':
                self._create_order_picking()
                self._compute_total_cost_in_real_time()

        if self.to_invoice and self.state == 'paid' and self.config_id.invoice_journal_id:
            self._generate_pos_order_invoice()
        elif not self.config_id.invoice_journal_id:
            _logger.warning('Trying to create an invoice without any journal configured')
            raise UserError(_('No invoice journal configured for this POS session.'))

        return self.id
