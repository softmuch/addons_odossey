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
        """KDS → Delivery state sync. Mapping: cooking→preparing, ready→ready, done→sent."""
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
            all_done = all(l.state == 'done' for l in active_lines)
            all_ready_or_done = all(l.state in ('ready', 'done') for l in active_lines)

            if any_cooking:
                target = 'preparing'
            elif all_done:
                target = 'sent'
            elif all_ready_or_done:
                target = 'ready'
            else:
                continue

            delivery = self.env['pos.delivery.order'].search([
                ('pos_order_uid', '=', pos_order.uuid),
                ('delivery_state', 'in', ['preparing', 'ready', 'sent']),
            ], limit=1)
            if not delivery or delivery.delivery_state == target:
                continue

            delivery.delivery_state = target
            config = delivery.pos_session_id.config_id or pos_order.session_id.config_id
            if config:
                config._notify('DELIVERY_STATE_CHANGE', {
                    'delivery_id': delivery.id,
                    'delivery_state': target,
                })
