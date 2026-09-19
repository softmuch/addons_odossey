# License OPL-1
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _reconcile_purchase_advance_payments(self):
        super()._reconcile_purchase_advance_payments()
        for bill in self:
            # Never let a reconciliation problem stop the bill from posting.
            try:
                with self.env.cr.savepoint():
                    bill._reconcile_consumed_supplier_credits()
            except Exception:
                _logger.exception(
                    "Could not reconcile the supplier credit consumed by the "
                    "orders of bill %s", bill.display_name,
                )
                bill.message_post(body=self.env._(
                    "Could not reconcile the supplier credit consumed by the orders of "
                    "this bill: use 'Reconcile purchase advances' to retry."
                ))

    def _reconcile_consumed_supplier_credits(self):
        """A supplier credit consumed while the vendor bill did not exist yet
        (see `_consume_supplier_credit_for_order`) leaves the credit's own
        advance `account.payment` unreconciled. Once the bill is posted,
        reconcile, per order, the part of each such advance that the order
        consumed and that hasn't been applied to one of its bills yet --
        never more than that (the advance can also serve other orders)."""
        self.ensure_one()
        credit = self.env["pos.supplier.credit"].sudo()
        for order in self.line_ids.purchase_line_id.order_id:
            rows = credit.search([
                ("used_order_id", "=", order.id),
                ("amount", "<", 0),
                ("account_payment_id", "!=", False),
            ])
            for payment in rows.account_payment_id:
                consumed = -sum(rows.filtered(lambda r: r.account_payment_id == payment).mapped("amount"))
                advance_lines = payment.move_id.line_ids.filtered(
                    lambda l: l.account_type == "liability_payable"
                )
                # Already applied from this advance to a bill of this order
                already = sum(
                    p.amount for p in advance_lines.matched_credit_ids
                    if p.credit_move_id.move_id in order.invoice_ids
                )
                cap = consumed - already
                if cap <= 0:
                    continue
                bill_lines = self.line_ids.filtered(
                    lambda l: l.account_type == "liability_payable" and l.amount_residual < 0
                )
                self._reconcile_credit_advance(
                    advance_lines.filtered(lambda l: l.amount_residual > 0), bill_lines, cap
                )
