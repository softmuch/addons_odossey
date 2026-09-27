from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    travel_web_booking = fields.Boolean(string="Online Booking", copy=False, readonly=True)
    travel_withdrawal_date = fields.Datetime(
        string="Withdrawal Requested", copy=False, readonly=True,
        help="Date on which the customer used the withdrawal button (botón de arrepentimiento).")

    def _get_prepayment_required_amount(self):
        """Trips: the amount required online to confirm the booking is the deposit of the trip
        (fixed per passenger or percentage), or the full amount when no deposit is allowed."""
        self.ensure_one()
        if self.trip_id and self.require_payment and self.travel_web_booking:
            if self.prepayment_percent >= 1.0 or not self.travel_deposit_required:
                return self.amount_total
            return self.currency_id.round(min(self.travel_deposit_required, self.amount_total))
        return super()._get_prepayment_required_amount()

    def _travel_invoiced_amount(self):
        """Total of the customer invoices of the order (credit notes deducted), not cancelled."""
        self.ensure_one()
        moves = self.order_line.invoice_lines.move_id.filtered(
            lambda m: m.state != 'cancel' and m.move_type in ('out_invoice', 'out_refund'))
        return sum(-m.amount_total if m.move_type == 'out_refund' else m.amount_total
                   for m in moves)

    def _travel_web_balance_url(self):
        """Portal link to pay the balance of the booking."""
        self.ensure_one()
        if self.state != 'sale' or self.currency_id.is_zero(self.travel_amount_due):
            return False
        return self.get_portal_url(query_string=f'&payment_amount={self.travel_amount_due}')

    def action_travel_web_view(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self.get_portal_url(), 'target': 'new'}
