from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_printer_assignment_mode = fields.Selection(
        related='pos_config_id.printer_assignment_mode',
        readonly=False,
    )
    pos_user_printer_ids = fields.One2many(
        related='pos_config_id.user_printer_ids',
        readonly=False,
    )
