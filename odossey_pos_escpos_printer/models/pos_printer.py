from odoo import models, fields, _
from odoo.exceptions import ValidationError


class PosPrinter(models.Model):
    _inherit = 'pos.printer'

    printer_type = fields.Selection(
        selection_add=[('escpos_network', 'ESC/POS Network Printer (TCP)')],
        ondelete={'escpos_network': 'set default'},
    )
    escpos_ip = fields.Char(
        string='Printer IP / Hostname',
        help='IP address or hostname of the ESC/POS printer on the local network',
    )
    escpos_port = fields.Integer(
        string='Port',
        default=9100,
        help='TCP port the printer listens on (standard ESC/POS port is 9100)',
    )
    paper_width_mm = fields.Integer(
        string='Paper Width (mm)',
        default=80,
        help='Receipt paper width in millimetres. Common values: 80mm (full-width) or 58mm (narrow)',
    )

    @classmethod
    def _load_pos_data_fields(cls, config_id):
        fields = super()._load_pos_data_fields(config_id)
        fields += ['escpos_ip', 'escpos_port', 'paper_width_mm']
        return fields

    def action_test_connection(self):
        """Test TCP connectivity to the ESC/POS printer."""
        self.ensure_one()
        if self.printer_type != 'escpos_network':
            raise ValidationError(_('Only ESC/POS Network printers can be tested here.'))
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((self.escpos_ip, self.escpos_port or 9100))
            sock.close()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Successful'),
                    'message': _('Printer %s is reachable on %s:%s') % (
                        self.name, self.escpos_ip, self.escpos_port
                    ),
                    'type': 'success',
                },
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': _('Cannot reach %s:%s — %s') % (
                        self.escpos_ip, self.escpos_port, str(e)
                    ),
                    'type': 'danger',
                    'sticky': True,
                },
            }
