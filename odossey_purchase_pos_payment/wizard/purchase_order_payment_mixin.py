# License OPL-1
from odoo import models


class PurchaseOrderPaymentMixin(models.AbstractModel):
    _name = "purchase.order.payment.mixin"
    _description = "Shared logic to pay one or more purchase orders via pos.payment"

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
        return {
            "company_id": order.company_id.id,
            "partner_id": order.partner_id.id,
            "currency_id": order.currency_id.id,
            "amount": -amount,
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
