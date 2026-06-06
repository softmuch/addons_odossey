import json
from odoo import api, models


class PosPrinter(models.Model):
    _inherit = 'pos.printer'

    @api.model
    def _load_pos_data_domain(self, data):
        config_data = data['pos.config']['data'][0]
        fixed_ids = config_data.get('printer_ids', [])
        if config_data.get('printer_assignment_mode') == 'per_user':
            user_map = json.loads(config_data.get('user_printer_map') or '{}')
            user_printer_ids = [v for v in user_map.values() if isinstance(v, int)]
            all_ids = list(set(fixed_ids + user_printer_ids))
        else:
            all_ids = fixed_ids
        return [('id', 'in', all_ids)]
