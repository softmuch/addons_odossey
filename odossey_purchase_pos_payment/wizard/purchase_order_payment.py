# License OPL-1
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrderPayment(models.TransientModel):
    _name = "purchase.order.payment"
    _inherit = "purchase.order.payment.mixin"
    _description = "Pay a Purchase Order"

    purchase_order_id = fields.Many2one(
        comodel_name="purchase.order", required=True
    )
    company_id = fields.Many2one(related="purchase_order_id.company_id")
    currency_id = fields.Many2one(related="purchase_order_id.currency_id")
    payment_method_id = fields.Many2one(
        comodel_name="pos.payment.method",
        required=True,
        domain="[('company_id', '=', company_id), ('show_in_purchase', '=', True)]",
    )
    amount = fields.Monetary(required=True)
    payment_date = fields.Date(default=fields.Date.context_today, required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "amount" in fields_list and res.get("purchase_order_id"):
            order = self.env["purchase.order"].browse(res["purchase_order_id"])
            res["amount"] = order.amount_total - order.amount_paid
        return res

    def action_pay(self):
        self.ensure_one()
        order = self.purchase_order_id
        if self.amount <= 0:
            raise UserError(_("The amount to pay must be greater than zero."))
        self._pay_purchase_orders(
            self.company_id, order.partner_id, self.payment_method_id,
            self.payment_date, [(order, self.amount)],
        )
        return True
