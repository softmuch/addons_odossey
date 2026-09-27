from odoo import api, fields, models

# Law 26.522, art. 96: fee on the gross billing of radio services (% by category and band)
ENACOM_RATES = {
    # category: (AM, FM, low power)
    'a': (2.5, 2.5, 2.0),
    'b': (1.5, 2.0, 2.0),
    'c': (1.0, 1.5, 1.0),
    'd': (0.5, 1.0, 1.0),
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    radio_frequency = fields.Char(string="Frequency", help="e.g. FM 98.3 MHz")
    radio_signal = fields.Char(string="Call Sign", help="Call sign of the station (e.g. LRA 300).")
    radio_license = fields.Char(
        string="ENACOM License / Permit",
        help="Number of the license, permit or authorization of the broadcasting service "
             "granted by ENACOM, printed on the broadcast certificates.")
    radio_band = fields.Selection(
        selection=[('am', "AM"), ('fm', "FM"), ('low', "Low power FM")],
        string="Band", default='fm')
    radio_enacom_category = fields.Selection(
        selection=[
            ('a', "A - Autonomous City of Buenos Aires"),
            ('b', "B - Cities of 600,000 inhabitants or more"),
            ('c', "C - Cities of less than 600,000 inhabitants"),
            ('d', "D - Towns of less than 100,000 inhabitants"),
        ], string="ENACOM Category", default='c',
        help="Category of the location of the station for the fee of Law 26.522 (art. 96).")
    radio_enacom_rate = fields.Float(
        string="ENACOM Fee (%)", compute='_compute_radio_enacom_rate', store=True,
        readonly=False,
        help="Fee of Law 26.522 (art. 94-96) on the gross billing of advertising, net of the "
             "discounts and commissions actually invoiced. Computed from the category and the "
             "band; it can be changed.")
    radio_max_ad_minutes = fields.Float(
        string="Max. Advertising Minutes per Hour", default=14.0,
        help="Legal limit of advertising per clock hour (Law 26.522, art. 82 a: 14 minutes "
             "per hour for radio). The daily log never exceeds it.")
    radio_break_capacity = fields.Integer(string="Default Break Capacity (s)", default=180)
    radio_break_interval = fields.Integer(string="Break Every (min)", default=30)
    radio_break_offset = fields.Integer(
        string="First Break After (min)", default=25,
        help="Minutes after the start of the program for the first break.")
    radio_schedule_days = fields.Integer(
        string="Plan the Log Days Ahead", default=7,
        help="The scheduled action plans the daily log of the next N days.")
    radio_auto_confirm = fields.Boolean(
        string="Confirm Planned Spots Automatically", default=True,
        help="At the end of the day, the spots still planned are marked as aired. The "
             "operator only records the exceptions (spots not aired).")
    radio_suspend_days = fields.Integer(
        string="Suspend Advertisers Overdue (days)", default=0,
        help="Suspend the log of the advertisers with invoices overdue more than N days "
             "(0 = never).")
    radio_agency_commission_product_id = fields.Many2one(
        'product.product', string="Agency Commission Product",
        default=lambda self: self.env.ref('odossey_radio.product_agency_commission',
                                          raise_if_not_found=False),
        help="Product used for the agency commission (discount line on the invoice or "
             "commission bill of the agency).")
    radio_certificate_note = fields.Html(
        string="Certificate Note", translate=True,
        default=lambda self: self.env._(
            "<p>We certify that the advertising detailed above was broadcast on the dates "
            "and times indicated, according to the daily log of the station.</p>"))

    @api.depends('radio_enacom_category', 'radio_band')
    def _compute_radio_enacom_rate(self):
        for company in self:
            rates = ENACOM_RATES.get(company.radio_enacom_category)
            if not rates:
                company.radio_enacom_rate = 0.0
                continue
            index = {'am': 0, 'fm': 1, 'low': 2}.get(company.radio_band or 'fm', 1)
            company.radio_enacom_rate = rates[index]

    @api.model
    def _radio_set_default_commission_product(self):
        product = self.env.ref('odossey_radio.product_agency_commission', raise_if_not_found=False)
        if product:
            self.search([('radio_agency_commission_product_id', '=', False)]).write(
                {'radio_agency_commission_product_id': product.id})
