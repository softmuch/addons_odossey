from odoo import models, api


class PosOrderLine(models.Model):
    _inherit ="pos.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        # Avoid repeated UUID (a conflict between pos_split_bill_bits and abichinger_kitchen_screen modules)
        for vals in vals_list:
            if 'uuid' in vals:
                old_line = self.search([('uuid', '=', vals['uuid'])])
                if old_line:
                    return self
        return super(PosOrderLine, self).create(vals_list)