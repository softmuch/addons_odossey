# License OPL-1
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted.filtered(lambda m: m.move_type == "in_invoice")._reconcile_purchase_advance_payments()
        return posted

    @api.model
    def _reconcile_capped(self, advance_line, bill_line, cap):
        """Reconcile a supplier advance payable line (debit) against a bill
        payable line (credit), but never for more than `cap` (company
        currency). A plain `.reconcile()` always spends `min(advance
        residual, bill residual)` -- more than what that order actually
        paid when the advance also serves other orders (a shared check) or
        is a banked credit. Returns what was reconciled."""
        currency = advance_line.company_id.currency_id
        advance_residual = advance_line.amount_residual
        bill_residual = -bill_line.amount_residual
        to_apply = min(cap, advance_residual, bill_residual)
        if currency.compare_amounts(to_apply, 0) <= 0:
            return 0.0
        if currency.compare_amounts(to_apply, min(advance_residual, bill_residual)) == 0:
            # Not capped by `cap`: the standard path (full reconcile, exchange
            # difference...) already reconciles exactly this much.
            (advance_line | bill_line).reconcile()
            return to_apply

        def in_currency(line):
            """`to_apply` expressed in the line's own currency (pro rata to
            its residual)."""
            ratio = to_apply / abs(line.amount_residual)
            return line.currency_id.round(abs(line.amount_residual_currency) * ratio)

        self.env["account.partial.reconcile"].create({
            "debit_move_id": advance_line.id,
            "credit_move_id": bill_line.id,
            "amount": to_apply,
            "debit_amount_currency": in_currency(advance_line),
            "credit_amount_currency": in_currency(bill_line),
        })
        return to_apply

    @api.model
    def _reconcile_credit_advance(self, advance_lines, bill_lines, cap):
        """Apply up to `cap` of `advance_lines` (an advance payment) to
        `bill_lines`. Returns the amount applied."""
        applied = 0.0
        for advance_line in advance_lines:
            for bill_line in bill_lines:
                left = cap - applied
                if left <= 0:
                    return applied
                if advance_line.amount_residual <= 0 or bill_line.amount_residual >= 0:
                    continue
                applied += self._reconcile_capped(advance_line, bill_line, left)
        return applied

    def _reconcile_purchase_advance_payments(self):
        """A supplier payment made through the purchase payment wizards
        BEFORE the vendor bill existed is booked as an unreconciled advance
        `account.payment` (nothing to reconcile against yet, see
        `pos.payment._create_purchase_order_account_payment`). Once the bill
        is posted, reconcile that advance against it: otherwise the purchase
        order reads "Paid" (its `amount_paid` comes from the `pos.payment`
        rows) while the bill stays open, inviting a second payment.

        Per order and per payment move, only what THAT order paid through
        it is applied (`pos.payment` amounts, minus what was already
        applied to a bill of the order): an existing check's single
        `account.payment` may cover several orders at once, and
        reconciling it whole here could spend part of it on this bill that
        was meant for another.
        """
        for bill in self:
            for order in bill.line_ids.purchase_line_id.order_id:
                for move in order.pos_payment_ids.account_move_id:
                    paid = sum(
                        abs(p.amount) for p in order.pos_payment_ids
                        if p.account_move_id == move
                    )
                    advance_lines = move.line_ids.filtered(
                        lambda l: l.account_type == "liability_payable"
                    )
                    already = sum(
                        p.amount for p in advance_lines.matched_credit_ids
                        if p.credit_move_id.move_id in order.invoice_ids
                    )
                    cap = paid - already
                    if cap <= 0:
                        continue
                    bill_lines = bill.line_ids.filtered(
                        lambda l: l.account_type == "liability_payable" and l.amount_residual < 0
                    )
                    self._reconcile_credit_advance(
                        advance_lines.filtered(lambda l: l.amount_residual > 0), bill_lines, cap
                    )

    def action_reconcile_purchase_advances(self):
        """Manual/cron retry of the advance reconciliation; a failure is
        logged in the bill's chatter instead of being lost."""
        for bill in self:
            try:
                with self.env.cr.savepoint():
                    bill._reconcile_purchase_advance_payments()
            except Exception as e:
                _logger.exception("Could not reconcile the advances of bill %s", bill.display_name)
                bill.message_post(body=self.env._(
                    "Could not reconcile the purchase advance payments of this bill: %s", e
                ))
        return True
