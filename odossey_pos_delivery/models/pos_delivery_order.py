from odoo import models, fields, api


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

    @api.model
    def sync_kds_states(self, session_id=False):
        """Update preparing→ready when all KDS lines are done. No hard dep on KDS."""
        if 'ab_pos.order.change.line' not in self.env.registry:
            return True
        domain = [('delivery_state', '=', 'preparing'), ('pos_order_id', '!=', False)]
        if session_id:
            domain.append(('pos_session_id', '=', session_id))
        preparing = self.search(domain)
        for delivery in preparing:
            changes = self.env['ab_pos.order.change'].search(
                [('order_id', '=', delivery.pos_order_id.id)]
            )
            if not changes:
                continue
            all_lines = changes.mapped('lines')
            if not all_lines:
                continue
            if all(l.state in ('ready', 'done', 'cancelled') for l in all_lines):
                delivery.write({'delivery_state': 'ready'})
        return True
