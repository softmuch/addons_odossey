from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Forecast
    travel_cancel_rate_pending = fields.Float(
        string="Cancellation Rate - Deposit Pending (%)", default=25.0,
        help="Estimated probability (%) that a confirmed booking whose deposit is not paid yet "
             "gets cancelled.")
    travel_cancel_rate_deposit = fields.Float(
        string="Cancellation Rate - Deposit Paid (%)", default=12.0,
        help="Estimated probability (%) that a booking with the deposit paid (price frozen) "
             "gets cancelled.")
    travel_cancel_rate_paid = fields.Float(
        string="Cancellation Rate - Fully Paid (%)", default=3.0,
        help="Estimated probability (%) that a fully paid booking gets cancelled.")
    travel_forecast_include_quotations = fields.Boolean(
        string="Include Quotations in Forecast", default=True,
        help="Also weight open quotations in the revenue forecast using the quotation win rate.")
    travel_quotation_win_rate = fields.Float(
        string="Quotation Win Rate (%)", default=30.0,
        help="Estimated probability (%) that an open travel quotation becomes a booking.")
    # Profitability
    travel_iibb_rate = fields.Float(
        string="IIBB Rate (%)", default=0.0,
        help="Rate (%) of the provincial gross income tax (Ingresos Brutos) used to estimate the "
             "tax in the net profitability report. It is not shown on invoices.")
    travel_iibb_base = fields.Selection(
        selection=[('revenue', "Net revenue"), ('margin', "Margin (revenue - supplier costs)")],
        string="IIBB Taxable Base", default='revenue', required=True,
        help="Travel agencies acting as intermediaries usually pay IIBB on their margin or "
             "commission. Confirm the base with your accountant.")
    travel_payment_fee_rate = fields.Float(
        string="Payment Fees Rate (%)", default=0.0,
        help="Estimated rate (%) of card/bank/payment gateway fees applied to the gross amount "
             "invoiced. Leave 0 if fees are recorded as vendor bills.")
    # Operations
    travel_passport_validity_months = fields.Integer(
        string="Passport Validity After Return (months)", default=6,
        help="Passports must be valid at least this number of months after the return date of "
             "international trips.")
    travel_invoice_service_dates = fields.Selection(
        selection=[('trip', "Trip dates"), ('invoice', "Invoice month (standard)")],
        string="ARCA Service Dates", default='trip', required=True,
        help="Service period informed to ARCA (concept Services) on invoices created from "
             "bookings.")
    travel_file_number = fields.Char(
        string="Travel Agency File Number",
        help="Registration number (legajo) of the travel agency in the national registry "
             "(Law 18.829). Printed on quotations.")
    travel_quotation_conditions = fields.Html(
        string="Quotation Conditions", translate=True,
        default=lambda self: self._default_travel_quotation_conditions())
    # Birthday emails
    travel_birthday_enabled = fields.Boolean(string="Send Birthday Emails", default=True)
    travel_birthday_template_id = fields.Many2one(
        'mail.template', string="Birthday Email Template",
        domain="[('model', '=', 'res.partner')]")

    @api.model
    def _default_travel_quotation_conditions(self):
        return self.env._(
            "<ul>"
            "<li>Rates subject to availability and confirmation at the time of booking.</li>"
            "<li>This is a quotation: no booking is made until the deposit is paid.</li>"
            "<li>The deposit freezes the price of the trip.</li>"
            "<li>Flight tickets are non-refundable; changes are subject to airline penalties.</li>"
            "<li>Passengers need a valid ID or passport (valid 6 months after return) and the "
            "visas required by the destination.</li>"
            "</ul>")
