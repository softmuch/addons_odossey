# License OPL-1
from odoo import api, fields, models


class PurchaseOrderPayment(models.TransientModel):
    _inherit = "purchase.order.payment"

    payment_method_type = fields.Selection(related="payment_method_id.payment_method_type")
    company_bank_ids = fields.Many2many(comodel_name="res.bank", compute="_compute_company_bank_ids")

    @api.depends("company_id")
    def _compute_company_bank_ids(self):
        for wizard in self:
            wizard.company_bank_ids = wizard._get_company_banks()


class PurchaseOrderPayFreely(models.TransientModel):
    _inherit = "purchase.order.pay.freely"

    payment_method_type = fields.Selection(related="payment_method_id.payment_method_type")
    company_bank_ids = fields.Many2many(comodel_name="res.bank", compute="_compute_company_bank_ids")

    @api.depends("company_id")
    def _compute_company_bank_ids(self):
        for wizard in self:
            wizard.company_bank_ids = wizard._get_company_banks()
