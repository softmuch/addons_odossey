from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    timesheet_sync_sale_qty = fields.Boolean(
        related='company_id.timesheet_sync_sale_qty', readonly=False)
