# License OPL-1
from odoo import fields, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    show_in_purchase = fields.Boolean(
        default=True,
        string="Show in Purchase",
        help="Offered as a payment method when paying a purchase order "
        "(Compras > Pagar / Pagar Libremente). Unchecked for a method "
        "like \"Cuenta de cliente\" that makes no sense on the supplier "
        "side.",
    )
