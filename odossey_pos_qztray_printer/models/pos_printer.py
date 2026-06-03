from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class PosPrinter(models.Model):
    _inherit = 'pos.printer'

    printer_type = fields.Selection(
        selection_add=[('qztray', 'QZ Tray (Browser → Local Printer)')],
        ondelete={'qztray': 'set default'},
    )

    # ── QZ Tray connection ────────────────────────────────────────────────────
    qztray_host = fields.Char(
        string='QZ Tray Host',
        default='localhost',
        help=(
            'Hostname or IP where QZ Tray is running. '
            'Usually "localhost" — QZ Tray runs on the same machine as the browser.'
        ),
    )
    qztray_port = fields.Integer(
        string='QZ Tray Port',
        default=8181,
        help='Secure WebSocket port for QZ Tray (default 8181). Insecure fallback uses port+1 (8182).',
    )

    # ── Printer mode ──────────────────────────────────────────────────────────
    qztray_mode = fields.Selection(
        selection=[
            ('os', 'OS Printer (by name)'),
            ('socket', 'Network Socket (ESC/POS raw TCP)'),
        ],
        string='Connection Mode',
        default='os',
        help=(
            'OS Printer: printer is installed in the operating system; '
            'QZ Tray uses the OS driver.\n'
            'Network Socket: printer accessible via IP:9100; '
            'QZ Tray opens a raw TCP connection (no OS driver needed).'
        ),
    )

    # ── OS printer mode ───────────────────────────────────────────────────────
    qztray_printer_name = fields.Char(
        string='OS Printer Name',
        help='Exact printer name as it appears in the OS (e.g. "EPSON TM-T20III"). Leave empty to use the default printer.',
    )

    # ── Socket mode ───────────────────────────────────────────────────────────
    qztray_socket_ip = fields.Char(
        string='Printer IP',
        help='IP address or hostname of the ESC/POS printer on the local network (socket mode).',
    )
    qztray_socket_port = fields.Integer(
        string='Printer Port',
        default=9100,
        help='TCP port the printer listens on. Standard ESC/POS port is 9100.',
    )

    # ── Shared ────────────────────────────────────────────────────────────────
    qztray_paper_width_mm = fields.Integer(
        string='Paper Width (mm)',
        default=80,
        help='Receipt paper width in millimetres. Common values: 80 mm or 58 mm.',
    )

    # ── Signing (optional — leave empty to use unsigned mode) ─────────────────
    qztray_certificate = fields.Text(
        string='QZ Tray Certificate',
        help=(
            'x509 digital certificate for silent (unsigned-dialog-free) printing. '
            'Obtain from qz.io or generate a self-signed pair. '
            'Leave empty to use unsigned mode (QZ Tray will show a one-time trust dialog).'
        ),
    )
    qztray_private_key = fields.Text(
        string='QZ Tray Private Key',
        help='PKCS#8 RSA private key paired with the certificate above. Stored in the database.',
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        result = super()._load_pos_data_fields(config_id)
        result += [
            'qztray_host',
            'qztray_port',
            'qztray_mode',
            'qztray_printer_name',
            'qztray_socket_ip',
            'qztray_socket_port',
            'qztray_paper_width_mm',
            'qztray_certificate',
            # private key stays server-side only — not sent to browser
        ]
        return result

    def action_test_qztray(self):
        """Return a notification — actual connectivity test is done client-side by QZ Tray JS."""
        self.ensure_one()
        if self.printer_type != 'qztray':
            raise ValidationError(_('Only QZ Tray printers can be tested here.'))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('QZ Tray Test'),
                'message': _(
                    'Open the POS session and try a test print. '
                    'QZ Tray must be running on the client machine at %s:%s.'
                ) % (self.qztray_host or 'localhost', self.qztray_port or 8181),
                'type': 'info',
            },
        }
