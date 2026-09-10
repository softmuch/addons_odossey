# License OPL-1
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrderPayFreely(models.TransientModel):
    _inherit = 'purchase.order.pay.freely'

    supplier_credit_balance = fields.Monetary(compute='_compute_supplier_credit_balance')

    def _compute_supplier_credit_balance(self):
        for wizard in self:
            wizard.supplier_credit_balance = wizard.partner_id.pos_supplier_credit_balance

    @api.onchange('partner_id')
    def _onchange_partner_id_amount(self):
        """Override (not extend): base sets `amount` to the raw open-orders
        total -- here it must already reflect the supplier credit discount,
        same as the partner is picked.
        """
        if self.partner_id:
            self.amount = self._credit_discounted_amount(
                self.currency_id, self._get_total_residual(), self.partner_id
            )

    @api.onchange('use_supplier_credit')
    def _onchange_use_supplier_credit(self):
        if self.partner_id:
            self.amount = self._credit_discounted_amount(
                self.currency_id, self._get_total_residual(), self.partner_id
            )

    def action_pay(self):
        """Full override (not calling `super()`): the base method rejects
        any amount beyond the supplier's total open balance
        (`_is_free_amount_entry` now always returns False here, so that
        rejection never fires) and never banks a leftover as credit. This
        adds, in order: (1) optionally consuming banked credit -- sized to
        the GAP between `self.amount` (already shown net of credit -- see
        `_onchange_partner_id_amount`/`_onchange_use_supplier_credit`) and
        the total open balance, applied against the OLDEST open order
        first, (2) the base module's own oldest-first distribution of
        `self.amount` itself (never reduced by the consumed credit -- it's
        already net of it, see `purchase.order.payment.action_pay` for why
        subtracting again would silently shortchange the total), and (3)
        banking whatever's left over the total open balance as new
        supplier credit instead of ever raising.
        """
        self.ensure_one()
        orders = self._get_open_orders()
        total_residual = sum(orders.mapped("amount_difference"))

        credit_gap = 0.0
        if self.use_supplier_credit and orders:
            credit_gap = max(
                self.company_id.currency_id.round(total_residual - self.amount), 0.0
            )
        # A $0 `amount` is only valid when banked credit is about to cover
        # the whole gap on its own -- otherwise it's a no-op the user
        # almost certainly didn't intend.
        if self.amount <= 0 and credit_gap <= 0:
            raise UserError(_("The amount to pay must be greater than zero."))

        if credit_gap > 0:
            self._consume_supplier_credit_for_order(
                orders[0], credit_gap, self.payment_method_id
            )

        remaining = self.amount
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
