# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    rioseed_lines_snapshot = fields.Json(copy=False)

    def action_open_pay_freely_wizard(self):
        """Moved here from account.move (used to live on the invoice list,
        applying payments to open invoices) -- now opens on pos.order's own
        list instead, applying `pos.payment`s to open POS orders. See
        `pay.freely.wizard` (models/pay_freely_wizard.py)."""
        return {
            'name': _('Pagar Libremente'),
            'type': 'ir.actions.act_window',
            'res_model': 'pay.freely.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_pos_order_set_draft(self):
        # odossey_partial_payments_pos's own action_pos_order_set_draft
        # assumes a 'partially_paid' order never generated a picking yet
        # ("nothing to undo" per its docstring) -- no longer true once this
        # module is installed: action_rioseed_confirm_edit can ALSO leave an
        # order 'partially_paid' after already creating real correction
        # pickings for it. Both modules add a header button named "Volver a
        # Borrador" that becomes visible at the same time on such an order
        # (see views/pos_order_views.xml's `picking_ids` addition to
        # odossey's button, which hides it once this applies) -- but the
        # method itself is overridden here too, in case it's ever invoked
        # some other way (API, another button), so behavior stays consistent
        # regardless of entry point: an order that already has pickings gets
        # routed through action_rioseed_reopen_draft() (captures
        # rioseed_lines_snapshot), everything else keeps odossey's original
        # behavior.
        already_cycled = self.filtered('picking_ids')
        for order in already_cycled:
            order.action_rioseed_reopen_draft()
        remaining = self - already_cycled
        if remaining:
            super(PosOrder, remaining).action_pos_order_set_draft()

    def action_rioseed_reopen_draft(self):
        self.ensure_one()
        if self.account_move or self.nb_print > 0:
            raise UserError(_("No se puede reabrir una orden facturada o con el ticket ya impreso."))
        if self.state not in ('paid', 'done', 'partially_paid'):
            raise UserError(_("Solo se puede reabrir una orden paga, registrada o parcialmente pagada."))
        self.rioseed_lines_snapshot = self._rioseed_lines_qty_by_product()
        # Core's write() refuses to move a 'paid'/'done' order to anything
        # outside ('paid', 'done', 'invoiced') -- see the "already been paid"
        # guard in point_of_sale/models/pos_order.py. Bypass it by writing
        # `state` through the base ORM directly.
        models.Model.write(self, {'state': 'draft'})

    def action_rioseed_confirm_edit(self):
        self.ensure_one()
        # Guard against calling this on an order that was never reopened (any
        # plain draft order, mid-checkout) or that already went through this
        # same method once (rioseed_lines_snapshot cleared to False at the end
        # of a legitimate run -- e.g. a stray double-click on "Confirmar"
        # before the button's `invisible` condition refreshes). Without this,
        # `original_by_product` below silently falls back to an empty
        # baseline, so every product currently on the order looks like a full
        # positive delta -- creating a spurious OUTGOING correction picking
        # for products that were never actually touched (or, if it fires a
        # second time after a real edit, for the products that were just
        # legitimately reduced).
        if self.state != 'draft' or not self.rioseed_lines_snapshot:
            raise UserError(_(
                "Esta orden no está en edición. Use \"Volver a Borrador\" antes de confirmar."
            ))

        original_by_product = {l['product_id']: l['qty'] for l in self.rioseed_lines_snapshot}
        current_by_product = {d['product_id']: d['qty'] for d in self._rioseed_lines_qty_by_product()}
        deltas = {}
        for product_id in set(original_by_product) | set(current_by_product):
            delta = current_by_product.get(product_id, 0.0) - original_by_product.get(product_id, 0.0)
            product = self.env['product.product'].browse(product_id)
            if product.type == 'consu' and not self.currency_id.is_zero(delta):
                deltas[product_id] = delta

        if deltas:
            self._rioseed_create_correction_pickings(deltas)

        self.rioseed_lines_snapshot = False
        self._compute_prices()
        # A payment removed/reduced while reopened can leave the order
        # underpaid even if it was fully 'paid'/'done' before -- restoring
        # `prev_state` blindly would misrepresent that. `partially_paid`
        # (odossey_partial_payments_pos) is the correct state whenever the
        # amounts no longer match, regardless of what the order was before.
        final_state = 'paid' if self._is_order_paid_with_rounding() else 'partially_paid'
        models.Model.write(self, {'state': final_state})

    def _rioseed_lines_qty_by_product(self):
        self.ensure_one()
        qty_by_product = {}
        for line in self.lines:
            qty_by_product[line.product_id.id] = qty_by_product.get(line.product_id.id, 0.0) + line.qty
        return [{'product_id': pid, 'qty': qty} for pid, qty in qty_by_product.items()]

    def _rioseed_create_correction_pickings(self, deltas):
        """Create correction picking(s) for the qty delta between the order's
        lines snapshot (taken on reopen) and their current state, without
        touching the original 'assigned' picking(s). Mirrors the
        picking_type/location resolution core uses for a normal delivery and
        for a refund (see `_create_order_picking`/
        `_create_picking_from_pos_order_lines` in point_of_sale's
        pos_order.py/stock_picking.py) but works on a plain
        {product_id: qty} dict since core's helpers always require a real
        `pos.order.line` recordset.
        """
        self.ensure_one()
        picking_type = self.config_id.picking_type_id
        if self.partner_id.property_stock_customer:
            destination_id = self.partner_id.property_stock_customer.id
        elif not picking_type or not picking_type.default_location_dest_id:
            destination_id = self.env['stock.warehouse']._get_partner_locations()[0].id
        else:
            destination_id = picking_type.default_location_dest_id.id

        positive = {pid: qty for pid, qty in deltas.items() if qty > 0}
        negative = {pid: -qty for pid, qty in deltas.items() if qty < 0}

        pickings = self.env['stock.picking']
        if positive:
            picking = self.env['stock.picking'].create(
                self.env['stock.picking']._prepare_picking_vals(
                    self.partner_id, picking_type, picking_type.default_location_src_id.id, destination_id,
                )
            )
            self._rioseed_create_moves(picking, positive, picking_type.default_location_src_id.id, destination_id)
            pickings |= picking
        if negative:
            if picking_type.return_picking_type_id:
                return_picking_type = picking_type.return_picking_type_id
            elif picking_type.warehouse_id.in_type_id:
                # The POS picking type has no return_picking_type_id configured
                # (common: it's a dedicated POS type, not the warehouse's own
                # Delivery/Receipt pair that core auto-links on warehouse
                # creation). Falling back to the same outgoing type here would
                # leave the correction picking with picking_type_code
                # 'outgoing' even though its locations are correctly reversed.
                # Use the warehouse's own Receipts type instead.
                return_picking_type = picking_type.warehouse_id.in_type_id
            else:
                return_picking_type = picking_type
            if return_picking_type != picking_type:
                return_location_id = return_picking_type.default_location_dest_id.id
            else:
                return_location_id = picking_type.default_location_src_id.id
            picking = self.env['stock.picking'].create(
                self.env['stock.picking']._prepare_picking_vals(
                    self.partner_id, return_picking_type, destination_id, return_location_id,
                )
            )
            self._rioseed_create_moves(picking, negative, destination_id, return_location_id)
            pickings |= picking

        pickings.write({'pos_session_id': self.session_id.id, 'pos_order_id': self.id, 'origin': self.name})
        pickings.action_confirm()
        pickings.action_assign()

    def _rioseed_create_moves(self, picking, qty_by_product, location_id, location_dest_id):
        move_vals = []
        for product_id, qty in qty_by_product.items():
            product = self.env['product.product'].browse(product_id)
            move_vals.append({
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'location_id': location_id,
                'location_dest_id': location_dest_id,
                'picking_id': picking.id,
                'picking_type_id': picking.picking_type_id.id,
                'company_id': self.company_id.id,
            })
        self.env['stock.move'].create(move_vals)
