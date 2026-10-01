from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    timesheet_noise_minutes = fields.Integer(
        string="Printed Hours Variation (minutes)",
        default=5,
        help="Maximum number of minutes added to or removed from each timesheet in the "
             "'+ Hours' reports of quotations and invoices. The variations of a sales "
             "order line always add up to zero, so the totals and the amounts do not change.\n"
             "Example with 5: entries of 00:30, 00:15 and 01:00 can be printed as 00:33, "
             "00:11 and 01:01 (total 01:45 in both cases).\n"
             "Set 0 to print the hours exactly as recorded.",
    )
