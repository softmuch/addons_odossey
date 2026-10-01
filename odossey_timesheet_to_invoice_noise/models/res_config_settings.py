from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    timesheet_noise_minutes = fields.Integer(
        related='company_id.timesheet_noise_minutes', readonly=False)
