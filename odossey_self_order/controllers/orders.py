# -*- coding: utf-8 -*-
from uuid import uuid4
from odoo import fields, http
from odoo.http import request
from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController


class OdosseySelfOrderController(PosSelfOrderController):

    # Re-declare route so Odoo routes to THIS class (not the parent),
    # ensuring self.process_order_args() calls our override below.
    @http.route("/pos-self-order/process-order/<device_type>/", auth="public", type="json", website=True)
    def process_order(self, order, access_token, table_identifier, device_type):
        return self.process_order_args(order, access_token, table_identifier, device_type)

    def process_order_args(self, order, access_token, table_identifier, device_type, **kwargs):
        # If a non-draft order already holds this UUID (e.g. previously cancelled),
        # replace the UUID so sync_from_ui creates a fresh order instead of
        # resurrecting the old one.
        order_uuid = order.get('uuid')
        if order_uuid:
            stale = request.env['pos.order'].sudo().search(
                [('uuid', '=', order_uuid), ('state', '!=', 'draft')], limit=1
            )
            if stale:
                order = dict(order)
                order['uuid'] = str(uuid4())

        result = super().process_order_args(
            order, access_token, table_identifier, device_type, **kwargs
        )

        order_ids = [o['id'] for o in result.get('pos.order', []) if o.get('id')]
        if order_ids:
            pos_orders = request.env['pos.order'].sudo().browse(order_ids)
            for pos_order in pos_orders:
                self._create_kds_change(pos_order)

        return result

    def _create_kds_change(self, order):
        existing_uuids = set(order.ab_pos_changes.lines.mapped('line_uuid'))
        new_lines = order.lines.filtered(
            lambda l: l.uuid not in existing_uuids and l.qty > 0
        )
        if not new_lines:
            return

        change = request.env['ab_pos.order.change'].sudo().create({
            'order_id': order.id,
            'sequence_number': len(order.ab_pos_changes) + 1,
            'created_at': fields.Datetime.now(),
        })
        for line in new_lines:
            request.env['ab_pos.order.change.line'].sudo().create({
                'change_id': change.id,
                'product_id': line.product_id.id,
                'qty': line.qty,
                'note': line.note or '',
                'line_uuid': line.uuid,
                'state': 'cooking',
                'attribute_value_ids': [(6, 0, line.attribute_value_ids.ids)],
            })

        # Re-trigger KDS notification so it picks up the freshly-created change records.
        # The precommit callback fires once before commit; by then all records above exist.
        order.note_order_change()
