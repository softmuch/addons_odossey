# License OPL-1
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrderPayFreely(models.TransientModel):
    _name = "purchase.order.pay.freely"
    _inherit = "purchase.order.payment.mixin"
    _description = "Pay Freely a Supplier's Open Purchase Orders"

    company_id = fields.Many2one(
        comodel_name="res.company", default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        required=True,
        domain="[('supplier_rank', '>', 0)]",
    )
    payment_method_id = fields.Many2one(
        comodel_name="pos.payment.method",
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
    amount = fields.Monetary(required=True)
    payment_date = fields.Date(default=fields.Date.context_today, required=True)

    def _get_open_orders(self):
        self.ensure_one()
        orders = self.env["purchase.order"].search([
            ("partner_id", "=", self.partner_id.id),
            ("company_id", "=", self.company_id.id),
            ("state", "=", "purchase"),
        ])
        return orders.filtered(lambda o: o.amount_difference > 0).sorted("date_order")

    def _get_total_residual(self):
        self.ensure_one()
        return sum(self._get_open_orders().mapped("amount_difference"))

    @api.onchange("partner_id")
    def _onchange_partner_id_amount(self):
        if self.partner_id:
            self.amount = self._get_total_residual()

    @api.onchange("amount")
    def _onchange_amount_cap(self):
        if self.partner_id and self._is_free_amount_entry():
            total_residual = self._get_total_residual()
            if self.amount > total_residual:
                self.amount = total_residual

    def _is_free_amount_entry(self):
        """True when `amount` is a number the user typed in and should be
        capped/validated against the total open balance. False when it's
        instead driven by a fixed real-world instrument (e.g. handing over
        an existing check for its own face value in
        `odossey_purchase_pos_payment_check`) -- overpaying relative to
        currently-open orders is then a normal, valid outcome (the
        supplier ends up with a credit balance), not a mistake to block.
        """
        return True

    def action_pay(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_("The amount to pay must be greater than zero."))
        orders = self._get_open_orders()
        total_residual = sum(orders.mapped("amount_difference"))
        if self._is_free_amount_entry() and self.amount > total_residual:
            raise UserError(_(
                "The amount exceeds this supplier's total open balance "
                "(%(total)s).", total=total_residual,
            ))

        remaining = self.amount
        order_amounts = []
        for order in orders:
            if remaining <= 0:
                break
            applied = min(remaining, order.amount_difference)
            order_amounts.append((order, applied))
            remaining -= applied

        self._pay_purchase_orders(
            self.company_id, self.partner_id, self.payment_method_id,
            self.payment_date, order_amounts,
        )
        return True
