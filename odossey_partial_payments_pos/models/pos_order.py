# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero

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

    def action_pos_order_paid(self):
        """Allow an order to be saved/finalized when it is only partially paid.

        Core's implementation computes the same "isPaid" boolean used by
        ``_is_pos_order_paid`` (with an extra cash-rounding tolerance on top)
        and raises a ``UserError`` as soon as the order is not fully paid.

        We always call ``super()`` first so a fully paid order (including
        one only "paid" thanks to core's cash-rounding tolerance) behaves
        100% like stock Odoo, ending in ``state == 'paid'``. We only step in
        when core raises that specific "not fully paid" error: if some money
        did come in (``amount_paid`` > 0), that's a deliberate partial
        payment, so we flag the order as ``partially_paid`` instead of
        blocking the save (stock/invoicing are left untouched, see our
        override of ``_process_saved_order`` below). If nothing at all was
        paid, that's not a "partial payment", it's "no payment", so we
        re-raise core's original error unchanged.
        """
        self.ensure_one()

        not_fully_paid_error = str(_("Order %s is not fully paid.", self.name))

        try:
            return super().action_pos_order_paid()
        except UserError as error:
            if str(error) != not_fully_paid_error or float_is_zero(
                self.amount_paid, precision_rounding=self.currency_id.rounding
            ):
                # Either a different error (e.g. raised by another module
                # further down the inheritance chain) or there was really no
                # payment at all: keep core's original behavior.
                raise

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
