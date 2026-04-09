from odoo import models, fields


class PosOrder(models.Model):
    _inherit = 'pos.order'


    def write(self, vals):
        vals['nb_print'] = 0
        return super(PosOrder, self).write(vals)