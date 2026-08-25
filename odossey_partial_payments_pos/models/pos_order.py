# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

import logging

from odoo import _, fields, models
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
