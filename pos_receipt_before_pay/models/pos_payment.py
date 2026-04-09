from odoo import models, api


class PosPayment(models.Model):

    _inherit = "pos.payment"

    @api.constrains('amount')
    def _check_amount(self):
        pass