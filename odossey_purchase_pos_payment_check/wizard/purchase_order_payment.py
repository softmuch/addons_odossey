# License OPL-1
from odoo import fields, models


class PurchaseOrderPayment(models.TransientModel):
    _inherit = "purchase.order.payment"

    payment_method_type = fields.Selection(related="payment_method_id.payment_method_type")


class PurchaseOrderPayFreely(models.TransientModel):
    _inherit = "purchase.order.pay.freely"

    payment_method_type = fields.Selection(related="payment_method_id.payment_method_type")
