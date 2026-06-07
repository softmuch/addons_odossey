from odoo import models, fields


class PosOrder(models.Model):
    _inherit = 'pos.order'

    is_delivery = fields.Boolean(string='Is Delivery', default=False)
