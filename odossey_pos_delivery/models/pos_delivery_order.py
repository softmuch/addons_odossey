from odoo import models, fields


class PosDeliveryOrder(models.Model):
    _name = 'pos.delivery.order'
    _description = 'POS Delivery Order'
    _order = 'start_time desc'

    partner_id = fields.Many2one('res.partner', string='Cliente')
    partner_name = fields.Char(string='Nombre')
    partner_phone = fields.Char(string='Teléfono')
    delivery_address = fields.Char(string='Dirección')
    note = fields.Text(string='Notas')
    delivery_state = fields.Selection([
        ('preparing', 'En preparación'),
        ('ready', 'Listo'),
        ('sent', 'Enviado'),
        ('delivered', 'Entregado'),
    ], default='preparing', string='Estado', required=True)
    payment_state = fields.Selection([
        ('paid', 'Pagado'),
        ('unpaid', 'No Pagado'),
    ], default='unpaid', string='Estado de pago', required=True)
    amount_total = fields.Float(string='Total', digits=(12, 2))
    start_time = fields.Datetime(string='Hora inicio', default=fields.Datetime.now)
    pos_order_id = fields.Many2one('pos.order', string='Orden POS', ondelete='set null')
    pos_session_id = fields.Many2one('pos.session', string='Sesión POS', ondelete='set null')
    estimated_time = fields.Integer(string='Tiempo estimado (min)')
    shipping_cost = fields.Float(string='Costo de envío', digits=(12, 2))