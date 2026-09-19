# License OPL-1
from odoo import api, fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    # A supplier payment is stored with a NEGATIVE `amount`
    # (`odossey_purchase_pos_payment`); these positive mirrors are for the
    # "purchase orders paid" tab of a check.
    paid_amount = fields.Monetary(string="Importe pagado", compute="_compute_paid_amounts")
    paid_reference_amount = fields.Monetary(
        string="Importe en moneda de la orden",
        currency_field="reference_currency_id",
        compute="_compute_paid_amounts",
    )

    @api.depends("amount", "reference_amount")
    def _compute_paid_amounts(self):
        for payment in self:
            payment.paid_amount = abs(payment.amount)
            payment.paid_reference_amount = abs(payment.reference_amount)
