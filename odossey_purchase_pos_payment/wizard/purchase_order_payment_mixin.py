# License OPL-1
from odoo import models


class PurchaseOrderPaymentMixin(models.AbstractModel):
    _name = "purchase.order.payment.mixin"
    _description = "Shared logic to pay one or more purchase orders via pos.payment"

    def _split_amount_for_credit(self):
        """`(money_amount, credit_extra)`: how much of `amount` goes through
        the chosen payment method as real money, and how much of it must
        instead come out of the supplier's banked credit (a separate
        payment). By default it's all money. Overridden e.g. when handing
        over an existing check, whose fixed value can't absorb more than
        its face amount (see `odossey_purchase_pos_payment_check`)."""
        self.ensure_one()
        return self.amount, 0.0

    def _get_existing_instrument_account_payment(self):
        """The `account.payment` of a fixed-value instrument (an existing
        check handed over, see `odossey_purchase_pos_payment_check`) that
        already covers whatever exceeds the orders paid -- so that surplus
        is booked as supplier credit against THAT payment instead of a
        second, duplicated one. Empty by default."""
        self.ensure_one()
        return self.env["account.payment"]

    def _get_rate(self, currency):
        """Company currency units per 1 unit of `currency`. Wizards that let
        the user type the rate override this and fall back to `super()`."""
        self.ensure_one()
        company_currency = self.company_id.currency_id
        if not currency or currency == company_currency:
            return 1.0
        return self.env["res.currency"]._get_conversion_rate(
            currency, company_currency, self.company_id, self.payment_date
        )

    def _get_order_residual(self, order):
        """What `order` still owes, in the company currency."""
        self.ensure_one()
        return self.company_id.currency_id.round(
            order.amount_difference * self._get_rate(order.currency_id)
        )

    def _get_payment_currency_amounts(self, order, amount):
        """`(currency, reference_amount)` for a payment of `amount` (company
        currency) against `order`. The payment is booked in the company
        currency; `reference_amount` is its equivalent in the order's own
        currency (what settles the order), from the wizard's exchange rate.
        Paying the whole residual settles it exactly, without a stray cent
        from the round trip through the rate.
        """
        company_currency = order.company_id.currency_id
        if order.currency_id == company_currency:
            return company_currency, amount
        rate = self._get_rate(order.currency_id)
        residual = order.amount_difference
        if amount >= self._get_order_residual(order):
            reference = residual
        else:
            reference = min(order.currency_id.round(amount / rate), residual)
        return company_currency, reference

    def _get_pos_payment_vals(self, order, amount, payment_method, payment_date):
        """Isolated as its own method (instead of inlined in the loop below)
        so an extension module (e.g. one adding cheque fields to this
        wizard) can override it to add extra vals per payment, without
        having to reimplement the whole loop.

        `pos_order_id` is deliberately left empty (default `False`) -- a
        supplier payment isn't a POS sale, there's nothing real to attach
        it to. `company_id`/`partner_id`/`currency_id` are normally
        `related` fields sourced FROM `pos_order_id`, so they're set here
        explicitly instead (see `pos.payment`'s own field overrides in
        `models/pos_payment.py` for why that's possible: a related field
        needs `readonly=False` before an explicit value in `create()`
        actually sticks, instead of being silently recomputed away).
        """
        currency, reference_amount = self._get_payment_currency_amounts(order, amount)
        return {
            "company_id": order.company_id.id,
            "partner_id": order.partner_id.id,
            "currency_id": currency.id,
            "amount": -amount,
            "reference_amount": -reference_amount,
            "payment_method_id": payment_method.id,
            "payment_date": payment_date,
            "purchase_order_id": order.id,
        }

    def _pay_purchase_orders(self, company, partner, payment_method, payment_date, order_amounts):
        """One negative `pos.payment` per `(purchase.order, amount)` pair in
        `order_amounts`, with no `pos.order` attached at all. Each payment's
        own `create()` (overridden in `models/pos_payment.py`) immediately
        posts and reconciles the matching `account.payment` -- nothing more
        is needed here beyond creating the rows.
        """
        for order, amount in order_amounts:
            self.env["pos.payment"].create(
                self._get_pos_payment_vals(order, amount, payment_method, payment_date)
            )
