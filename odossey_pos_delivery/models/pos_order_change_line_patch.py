from odoo import models


class PosOrderChangeLineDelivery(models.Model):
    _inherit = 'ab_pos.order.change.line'

    def write(self, vals):
        res = super().write(vals)
        # skip_delivery_sync prevents loop when Delivery screen syncs state to KDS
        if 'state' in vals and not self.env.context.get('skip_delivery_sync'):
            self._sync_delivery_state()
        return res

    def _sync_delivery_state(self):
        """Bidirectional KDS ↔ Delivery state sync triggered by KDS line writes."""
        for pos_order in self.mapped('change_id.order_id'):
            if not pos_order.uuid:
                continue
            active_lines = self.env['ab_pos.order.change.line'].search([
                ('change_id.order_id', '=', pos_order.id),
                ('state', '!=', 'cancel'),
            ])
            if not active_lines:
                continue

            any_cooking = any(l.state == 'cooking' for l in active_lines)
            all_ready_or_done = all(l.state in ('ready', 'done') for l in active_lines)

            delivery = self.env['pos.delivery.order'].search([
                ('pos_order_uid', '=', pos_order.uuid),
                ('delivery_state', 'in', ['preparing', 'ready']),
            ], limit=1)
            if not delivery:
                continue

            new_state = None
            if all_ready_or_done and delivery.delivery_state == 'preparing':
                new_state = 'ready'
            elif any_cooking and delivery.delivery_state == 'ready':
                new_state = 'preparing'

            if new_state:
                delivery.delivery_state = new_state
                config = delivery.pos_session_id.config_id
                if config:
                    config._notify('DELIVERY_STATE_CHANGE', {
                        'delivery_id': delivery.id,
                        'delivery_state': new_state,
                    })
