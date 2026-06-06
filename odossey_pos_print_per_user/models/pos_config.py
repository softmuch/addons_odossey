import json
from odoo import fields, models, api


class PosConfig(models.Model):
    _inherit = 'pos.config'

    printer_assignment_mode = fields.Selection(
        [('fixed', 'Fixed Printer'), ('per_user', 'Printer per User')],
        string='Printer Assignment Mode',
        default='fixed',
        required=True,
    )
    user_printer_ids = fields.One2many(
        'odossey.pos.user.printer', 'config_id', string='User Printers'
    )

    @api.depends(
        'user_printer_ids.user_id',
        'user_printer_ids.printer_id',
        'user_printer_ids.receipt_printer_id',
    )
    def _compute_user_printer_map(self):
        for config in self:
            config.user_printer_map = json.dumps(
                {str(r.user_id.id): r.printer_id.id for r in config.user_printer_ids}
            )
            config.user_receipt_printer_map = json.dumps(
                {
                    str(r.user_id.id): r.receipt_printer_id.id
                    for r in config.user_printer_ids
                    if r.receipt_printer_id
                }
            )

    user_printer_map = fields.Char(
        compute='_compute_user_printer_map',
        store=True,
        string='User Preparation Printer Map (JSON)',
    )
    user_receipt_printer_map = fields.Char(
        compute='_compute_user_printer_map',
        store=True,
        string='User Receipt Printer Map (JSON)',
    )

