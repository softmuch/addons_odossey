from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PosDeliveryOrder(models.Model):
    _name = 'pos.delivery.order'
    _description = 'POS Delivery Order'
    _order = 'start_time desc'

    partner_id = fields.Many2one('res.partner', string='Customer')
    partner_name = fields.Char(string='Name')
    partner_phone = fields.Char(string='Phone')
    delivery_address = fields.Char(string='Address')
    note = fields.Text(string='Notes')
    delivery_state = fields.Selection([
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
    ], default='preparing', string='State', required=True)
    payment_state = fields.Selection([
        ('paid', 'Paid'),
        ('unpaid', 'Unpaid'),
    ], default='unpaid', string='Payment State', required=True)
    amount_total = fields.Float(string='Total', digits=(12, 2))
    start_time = fields.Datetime(string='Start Time', default=fields.Datetime.now)
    pos_order_id = fields.Many2one('pos.order', string='POS Order', ondelete='set null')
    pos_session_id = fields.Many2one('pos.session', string='POS Session', ondelete='set null')
    estimated_time = fields.Integer(string='Estimated Time (min)')
    shipping_cost = fields.Float(string='Shipping Cost', digits=(12, 2))
    pos_order_uid = fields.Char(string='POS Order UUID')
    hidden = fields.Boolean(string='Hidden', default=False)

    def unlink(self):
        has_kds = 'ab_pos.order.change.line' in self.env.registry
        orders_to_cancel = self.env['pos.order']
        for delivery in self:
            if not delivery.pos_order_uid:
                continue
            pos_order = self.env['pos.order'].search(
                [('uuid', '=', delivery.pos_order_uid)], limit=1
            )
            if not pos_order:
                continue
            if pos_order.state == 'draft':
                if pos_order.payment_ids:
                    raise UserError(_(
                        "Order %s has registered payments. Open it and finish or "
                        "remove the payment before deleting it.",
                        pos_order.pos_reference or pos_order.name,
                    ))
                # Deleting an unpaid delivery must not leave its draft POS order
                # behind: it would be unreachable and block the session closing.
                orders_to_cancel |= pos_order
            if not has_kds:
                continue
            change_lines = self.env['ab_pos.order.change.line'].search([
                ('change_id.order_id', '=', pos_order.id),
                ('state', '!=', 'cancel'),
            ])
            if change_lines:
                # skip_delivery_sync prevents our write() override from re-triggering
                change_lines.with_context(skip_delivery_sync=True).write({'state': 'cancel'})
                pos_order.note_order_change()
        res = super().unlink()
        if orders_to_cancel:
            # draft-only; notifies every terminal so they drop the order from memory
            orders_to_cancel.action_pos_order_cancel()
        return res

    @api.model
    def _adopt_orphan_delivery_orders(self, session_id):
        """Safety net: create the missing delivery record for draft delivery orders
        of the session, so they are always reachable from the Delivery screen."""
        if not session_id:
            return
        # grace period: do not race the POS client creating its own record
        limit_dt = fields.Datetime.subtract(fields.Datetime.now(), minutes=1)
        orders = self.env['pos.order'].search([
            ('session_id', '=', session_id),
            ('state', '=', 'draft'),
            ('is_delivery', '=', True),
            ('lines', '!=', False),
            ('write_date', '<', limit_dt),
        ])
        if not orders:
            return
        known = set(self.search(
            [('pos_order_uid', 'in', orders.mapped('uuid'))]
        ).mapped('pos_order_uid'))
        for order in orders.filtered(lambda o: o.uuid not in known):
            partner = order.partner_id
            self.create({
                'partner_id': partner.id,
                'partner_name': partner.name or '',
                'partner_phone': partner.phone or partner.mobile or '',
                'delivery_address': ', '.join(filter(None, [partner.street, partner.city, partner.zip])),
                'amount_total': order.amount_total,
                'pos_session_id': session_id,
                'pos_order_uid': order.uuid,
                'start_time': order.date_order,
                'delivery_state': 'preparing',
                'payment_state': 'unpaid',
            })

    @api.model
    def sync_kds_states(self, session_id=False):
        """Fallback: update preparing→ready when all KDS lines are off cooking state.
        Also hides delivery orders whose linked POS order has been cancelled."""
        self._adopt_orphan_delivery_orders(session_id)
        # Hide delivery orders whose POS order is cancelled
        hide_domain = [('hidden', '=', False), ('pos_order_uid', '!=', False)]
        if session_id:
            hide_domain.append(('pos_session_id', '=', session_id))
        for delivery in self.search(hide_domain):
            pos_order = self.env['pos.order'].search(
                [('uuid', '=', delivery.pos_order_uid), ('state', '=', 'cancel')], limit=1
            )
            if pos_order:
                delivery.write({'hidden': True})

        if 'ab_pos.order.change.line' not in self.env.registry:
            return True
        domain = [('delivery_state', '=', 'preparing'), ('pos_order_uid', '!=', False), ('hidden', '=', False)]
        if session_id:
            domain.append(('pos_session_id', '=', session_id))
        for delivery in self.search(domain):
            pos_order = self.env['pos.order'].search(
                [('uuid', '=', delivery.pos_order_uid)], limit=1
            )
            if not pos_order:
                continue
            active_lines = self.env['ab_pos.order.change.line'].search([
                ('change_id.order_id', '=', pos_order.id),
                ('state', '!=', 'cancel'),
            ])
            if not active_lines:
                continue
            if all(l.state in ('ready', 'done') for l in active_lines):
                delivery.write({'delivery_state': 'ready'})
        return True

    @api.model
    def sync_delivery_to_kds(self, delivery_id=False, new_delivery_state=False):
        """Called from POS JS when delivery state changes — update KDS change lines."""
        if 'ab_pos.order.change.line' not in self.env.registry:
            return True
        if not delivery_id or not new_delivery_state:
            return True

        KDS_STATE_MAP = {
            'preparing': 'cooking',
            'ready': 'ready',
            'sent': 'done',
            'delivered': 'done',
        }
        kds_state = KDS_STATE_MAP.get(new_delivery_state)
        if not kds_state:
            return True

        delivery = self.browse(delivery_id)
        if not delivery.exists() or not delivery.pos_order_uid:
            return True

        pos_order = self.env['pos.order'].search(
            [('uuid', '=', delivery.pos_order_uid)], limit=1
        )
        if not pos_order:
            return True

        change_lines = self.env['ab_pos.order.change.line'].search([
            ('change_id.order_id', '=', pos_order.id),
            ('state', '!=', 'cancel'),
            ('state', '!=', kds_state),
        ])
        if change_lines:
            # skip_delivery_sync prevents our write() override from re-triggering
            change_lines.with_context(skip_delivery_sync=True).write({'state': kds_state})
            pos_order.note_order_change()
        return True
