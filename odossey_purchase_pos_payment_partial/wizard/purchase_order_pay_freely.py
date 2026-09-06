# License OPL-1
from odoo import _, fields, models
from odoo.exceptions import UserError


class PurchaseOrderPayFreely(models.TransientModel):
    _inherit = 'purchase.order.pay.freely'

    supplier_credit_balance = fields.Monetary(compute='_compute_supplier_credit_balance')

    def _compute_supplier_credit_balance(self):
        for wizard in self:
            wizard.supplier_credit_balance = wizard.partner_id.pos_supplier_credit_balance

    def action_pay(self):
        """Full override (not calling `super()`): the base method rejects
        any amount beyond the supplier's total open balance
        (`_is_free_amount_entry` now always returns False here, so that
        rejection never fires) and never banks a leftover as credit. This
        adds, in order: (1) optionally consuming banked credit against the
        OLDEST open order first (reducing how much real payment is needed
        before the distribution loop below even runs), (2) the base
        module's own oldest-first distribution across open orders
        unchanged, and (3) banking whatever's left over the total open
        balance as new supplier credit instead of ever raising.
        """
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_("The amount to pay must be greater than zero."))

        orders = self._get_open_orders()
        remaining = self.amount

        if self.use_supplier_credit and orders:
            remaining -= self._consume_supplier_credit_for_order(
                orders[0], remaining, self.payment_method_id
            )

        order_amounts = []
        for order in orders:
            if remaining <= 0:
                break
            applied = min(remaining, order.amount_difference)
            if applied <= 0:
                continue
            order_amounts.append((order, applied))
            remaining = self.company_id.currency_id.round(remaining - applied)

        if order_amounts:
            self._pay_purchase_orders(
                self.company_id, self.partner_id, self.payment_method_id,
                self.payment_date, order_amounts,
            )

        if remaining > 0:
            self._bank_supplier_credit(
                self.company_id, self.partner_id, self.payment_method_id,
                self.payment_date, remaining, orders[0] if orders else self.env['purchase.order'],
            )
        return True
