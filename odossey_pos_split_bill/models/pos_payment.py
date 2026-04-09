from odoo import models, api


class PosPayment(models.Model):
    _inherit ="pos.payment"

    @api.model_create_multi
    def create(self, vals_list):
        # Avoid repeated UUID (a conflict between odossey_pos_split_bill and abichinger_kitchen_screen modules)
        for vals in vals_list:
            if 'uuid' in vals:
                old_payment = self.search([('uuid', '=', vals['uuid'])])
                if old_payment:
                    return self
        return super(PosPayment, self).create(vals_list)