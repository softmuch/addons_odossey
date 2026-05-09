from odoo import models, fields

# In Odoo 18, pos.order inherits pos.load.mixin which exposes ALL fields
# to the JS frontend automatically. get_table_draft_orders, _order_fields
# and _export_for_ui no longer exist in Odoo 18.

class PosOrderV2(models.Model):
    _inherit = "pos.order"

    is_split = fields.Boolean("Is Split bill", default=False)
    to_split = fields.Integer("To Split", default=1)
    split_done = fields.Integer("Split Done", default=0)
    n_payments = fields.Integer("Nº Payments", default=1)

    def bill_made(self, order_id):
        order = self.browse(order_id)
        if order and order.is_split:
            res = order.write({"split_done": order.split_done + 1})
            return res