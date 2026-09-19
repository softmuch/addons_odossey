# License OPL-1
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PurchaseOrderPayFreelyRate(models.TransientModel):
    _name = "purchase.order.pay.freely.rate"
    _description = "Exchange rate used by Pay Freely for one foreign currency"

    wizard_id = fields.Many2one(
        comodel_name="purchase.order.pay.freely", required=True, ondelete="cascade"
    )
    company_currency_id = fields.Many2one(
        related="wizard_id.company_id.currency_id", string="Company Currency"
    )
    currency_id = fields.Many2one(comodel_name="res.currency", required=True, readonly=True)
    # Units of company currency per 1 unit of `currency_id`
    # (e.g. 1 USD = 1200 ARS -> rate = 1200).
    rate = fields.Float(
        string="Exchange Rate",
        digits=(16, 6),
        required=True,
        help="How many units of the company currency 1 unit of this "
        "currency is worth.",
    )

    @api.constrains("rate")
    def _check_rate(self):
        for line in self:
            if line.rate <= 0:
                raise ValidationError(self.env._("The exchange rate must be greater than zero."))
