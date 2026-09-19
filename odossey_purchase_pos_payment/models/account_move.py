# License OPL-1
from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted.filtered(lambda m: m.move_type == "in_invoice")._reconcile_purchase_advance_payments()
        return posted

    def _reconcile_purchase_advance_payments(self):
        """A supplier payment made through the purchase payment wizards
        BEFORE the vendor bill existed is booked as an unreconciled advance
        `account.payment` (nothing to reconcile against yet, see
        `pos.payment._create_purchase_order_account_payment`). Once the bill
        is posted, reconcile that advance against it: otherwise the purchase
        order reads "Paid" (its `amount_paid` comes from the `pos.payment`
        rows) while the bill stays open, inviting a second payment.

        Only the payment moves that belong to this order alone are used: an
        existing check's single `account.payment` may cover several orders
        at once, and reconciling it here could spend part of it on this
        bill that was meant for another.
        """
        for bill in self:
            for order in bill.line_ids.purchase_line_id.order_id:
                moves = order.pos_payment_ids.account_move_id.filtered(
                    lambda m: not (m.pos_payment_ids.purchase_order_id - order)
                )
                advance_lines = moves.line_ids.filtered(
                    lambda l: l.account_type == "liability_payable" and not l.reconciled
                )
                bill_lines = bill.line_ids.filtered(
                    lambda l: l.account_type == "liability_payable" and not l.reconciled
                )
                if advance_lines and bill_lines:
                    (advance_lines | bill_lines).reconcile()
