# License OPL-1
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrderPayment(models.TransientModel):
    _inherit = 'purchase.order.payment'

    # Base module's own field is required=True -- relaxed here since credit
    # alone can fully cover the order (amount ends up 0, see default_get/
    # _onchange_use_supplier_credit below), in which case no real payment
    # method is ever needed. `action_pay` still enforces it whenever
    # `amount > 0` (real money to tender), it just isn't a blind form-level
    # requirement anymore.
    payment_method_id = fields.Many2one(
        required=False,
        domain="[('company_id', '=', company_id), ('show_in_purchase', '=', True), "
        "('is_credit_transfer', '=', False)]",
    )
    supplier_credit_balance = fields.Monetary(compute='_compute_supplier_credit_balance')

    def _compute_supplier_credit_balance(self):
        for wizard in self:
            wizard.supplier_credit_balance = (
                wizard.purchase_order_id.partner_id.pos_supplier_credit_balance
            )

    @api.model
    def default_get(self, fields_list):
        """Discount the suggested `amount` (base module's own default: the
        order's full residual) by the supplier's banked credit, same as
        `pos.make.payment` does on the POS side -- so the form opens already
        showing what's actually left to pay in real money.
        """
        res = super().default_get(fields_list)
        if 'amount' not in fields_list or not res.get('purchase_order_id'):
            return res
        order = self.env['purchase.order'].browse(res['purchase_order_id'])
        wizard = self.new({'use_supplier_credit': res.get('use_supplier_credit', True)})
        res['amount'] = wizard._credit_discounted_amount(
            order.currency_id, res.get('amount', 0.0), order.partner_id
        )
        return res

    @api.onchange('use_supplier_credit')
    def _onchange_use_supplier_credit(self):
        order = self.purchase_order_id
        if not order:
            return
        residual = order.currency_id.round(order.amount_total - order.amount_paid)
        self.amount = self._credit_discounted_amount(order.currency_id, residual, order.partner_id)

    def action_pay(self):
        """Full override (not calling `super()`): the base method always
        applies its full `amount` to `self.purchase_order_id` alone. This
        module needs to, in order: (1) optionally consume banked supplier
        credit to cover the GAP between `self.amount` (already shown net of
        credit -- see `default_get`/`_onchange_use_supplier_credit`) and the
        order's real residual, (2) apply `self.amount` itself as a real
        payment to THIS order up to its own (now credit-reduced) residual,
        (3) redirect any leftover to the same supplier's other
        partially-paid orders, oldest first, and (4) bank whatever's left
        after that as new supplier credit -- instead of ever creating one
        oversized payment against a single bill.

        `self.amount` is deliberately never reduced by the consumed credit
        here -- it's already net of it. Subtracting again would silently
        shortchange the order by the credit amount (the earlier bug this
        replaces): consuming and paying are two independent contributions
        that both need to land in full, not one carved out of the other.
        """
        self.ensure_one()
        order = self.purchase_order_id
        residual = order.currency_id.round(order.amount_total - order.amount_paid)
        credit_gap = 0.0
        if self.use_supplier_credit:
            credit_gap = max(order.currency_id.round(residual - self.amount), 0.0)
        # A $0 `amount` is only valid when banked credit is about to cover
        # the whole gap on its own (e.g. residual == available credit,
        # nothing left to tender in real money) -- otherwise it's a no-op
        # the user almost certainly didn't intend.
        if self.amount <= 0 and credit_gap <= 0:
            raise UserError(_("The amount to pay must be greater than zero."))
        # A payment method is only actually needed for the real-money leg
        # below (`_pay_purchase_orders`/`_redistribute_purchase_overpayment`)
        # -- credit consumption uses its own dedicated "Crédito Cliente/
        # Proveedor" tender instead (see `_consume_supplier_credit_for_order`),
        # never the one picked here. Don't block on it when there's nothing
        # left to tender in real money.
        if self.amount > 0 and not self.payment_method_id:
            raise UserError(_("Select a payment method."))

        if credit_gap > 0:
            self._consume_supplier_credit_for_order(order, credit_gap)

        remaining = self.amount
        order_amounts = []
        if remaining > 0:
            # Re-derived, not reused from above: consuming credit just now
            # may have already reduced how much this order still owes.
            primary_residual = order.currency_id.round(order.amount_total - order.amount_paid)
            primary_amount = min(remaining, primary_residual)
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
