from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # {sales order line id: variation stored on that sales order line}
    timesheet_noise = fields.Json(string="Printed Hours Variation", copy=False)
