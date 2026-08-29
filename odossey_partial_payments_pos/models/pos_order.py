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
    state = fields.Selection(
        selection_add=[('partially_paid', 'Partially Paid')],
        ondelete={'partially_paid': 'set default'},
    )

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
