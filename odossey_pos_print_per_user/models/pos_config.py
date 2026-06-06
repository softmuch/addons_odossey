import json
from odoo import api, fields, models


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

    @api.depends('user_printer_ids.user_id', 'user_printer_ids.printer_id')
    def _compute_user_printer_map(self):
        for config in self:
            config.user_printer_map = json.dumps(
                {str(r.user_id.id): r.printer_id.id for r in config.user_printer_ids}
            )

    user_printer_map = fields.Char(
        compute='_compute_user_printer_map',
        store=True,
        string='User Printer Map (JSON)',
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        return super()._load_pos_data_fields(config_id) + [
            'printer_assignment_mode',
            'user_printer_map',
        ]
