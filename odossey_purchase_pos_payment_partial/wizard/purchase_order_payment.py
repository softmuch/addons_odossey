# License OPL-1
from odoo import _, fields, models
from odoo.exceptions import UserError


class PurchaseOrderPayment(models.TransientModel):
    _inherit = 'purchase.order.payment'

    supplier_credit_balance = fields.Monetary(compute='_compute_supplier_credit_balance')

    def _compute_supplier_credit_balance(self):
        for wizard in self:
            wizard.supplier_credit_balance = (
                wizard.purchase_order_id.partner_id.pos_supplier_credit_balance
            )

    def action_pay(self):
        """Full override (not calling `super()`): the base method always
        applies its full `amount` to `self.purchase_order_id` alone. This
        module needs to, in order: (1) optionally consume banked supplier
        credit first, (2) apply whatever real amount remains to THIS order
        up to its own residual, (3) redirect any leftover to the same
        supplier's other partially-paid orders, oldest first, and (4) bank
        whatever's left after that as new supplier credit -- instead of
        ever creating one oversized payment against a single bill.
        """
        self.ensure_one()
        order = self.purchase_order_id
        if self.amount <= 0:
            raise UserError(_("The amount to pay must be greater than zero."))

        remaining = self.amount
        if self.use_supplier_credit:
            remaining -= self._consume_supplier_credit_for_order(
                order, remaining, self.payment_method_id
            )

        order_amounts = []
        if remaining > 0:
            residual = order.currency_id.round(order.amount_total - order.amount_paid)
            primary_amount = min(remaining, residual)
            if primary_amount > 0:
                order_amounts.append((order, primary_amount))
                remaining = order.currency_id.round(remaining - primary_amount)

        if remaining > 0:
            order_amounts += self._redistribute_purchase_overpayment(
                order, self.payment_method_id, self.payment_date, remaining
            )

        if order_amounts:
            self._pay_purchase_orders(
                self.company_id, order.partner_id, self.payment_method_id,
                self.payment_date, order_amounts,
            )
        return True
