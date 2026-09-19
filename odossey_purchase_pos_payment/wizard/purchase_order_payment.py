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
    # `amount` is expressed in the company currency (`currency_id`), the
    # order's own currency being `order_currency_id`. They only differ for a
    # foreign-currency order, where `rate` converts between the two.
    currency_id = fields.Many2one(related="company_id.currency_id")
    order_currency_id = fields.Many2one(related="purchase_order_id.currency_id")
    foreign_currency = fields.Boolean(compute="_compute_foreign_currency")
    rate = fields.Float(
        string="Exchange Rate",
        digits=(16, 6),
        default=1.0,
        help="How many units of the company currency 1 unit of the "
        "order's currency is worth.",
    )
    payment_method_id = fields.Many2one(
        comodel_name="pos.payment.method",
        required=True,
        domain="[('company_id', '=', company_id), ('show_in_purchase', '=', True)]",
    )
    amount = fields.Monetary(required=True)
    payment_date = fields.Date(default=fields.Date.context_today, required=True)

    @api.depends("order_currency_id", "currency_id")
    def _compute_foreign_currency(self):
        for wizard in self:
            wizard.foreign_currency = wizard.order_currency_id != wizard.currency_id

    def _get_rate(self, currency):
        """The rate typed in the wizard for the order's own currency."""
        self.ensure_one()
        if (
            currency
            and currency == self.order_currency_id
            and currency != self.currency_id
            and self.rate > 0
        ):
            return self.rate
        return super()._get_rate(currency)

    def _get_default_amount(self):
        """What's left to pay on the order, in the company currency."""
        self.ensure_one()
        return self._get_order_residual(self.purchase_order_id)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get("purchase_order_id"):
            order = self.env["purchase.order"].browse(res["purchase_order_id"])
            wizard = self.new({
                "purchase_order_id": order.id,
                "payment_date": fields.Date.context_today(self),
            })
            res["rate"] = super(PurchaseOrderPayment, wizard)._get_rate(order.currency_id)
            if "amount" in fields_list:
                wizard.rate = res["rate"]
                res["amount"] = wizard._get_default_amount()
        return res

    @api.onchange("rate")
    def _onchange_rate(self):
        if self.purchase_order_id:
            self.amount = self._get_default_amount()

    def action_pay(self):
        self.ensure_one()
        order = self.purchase_order_id
        if self.amount <= 0:
            raise UserError(_("The amount to pay must be greater than zero."))
        if self.rate <= 0:
            raise UserError(_("The exchange rate must be greater than zero."))
        self._pay_purchase_orders(
            self.company_id, order.partner_id, self.payment_method_id,
            self.payment_date, [(order, self.amount)],
        )
        return True
