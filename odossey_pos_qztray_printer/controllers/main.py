import base64
import hashlib
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class QzTrayController(http.Controller):

    @http.route(
        '/pos/qztray/sign',
        type='json',
        auth='user',
        csrf=False,
        methods=['POST'],
    )
    def sign_message(self, message, printer_id=None, **kwargs):
        """
        Sign a QZ Tray challenge message with the private key stored in pos.printer.

        QZ Tray calls qz.security.setSignaturePromise() on the JS side, which
        POSTs the message here.  We sign it with SHA-512 + RSA and return the
        base64 signature.

        If no private key is configured the endpoint returns an empty string,
        which keeps QZ Tray in unsigned (dialog) mode.
        """
        try:
            # If a specific printer_id is passed, load the key from that printer.
            # Otherwise fall back to any configured qztray printer in the current session.
            private_key_pem = None

            if printer_id:
                printer = request.env['pos.printer'].sudo().browse(int(printer_id))
                if printer.exists():
                    private_key_pem = printer.qztray_private_key
            else:
                printer = request.env['pos.printer'].sudo().search(
                    [('printer_type', '=', 'qztray'), ('qztray_private_key', '!=', False)],
                    limit=1,
                )
                if printer:
                    private_key_pem = printer.qztray_private_key

            if not private_key_pem or not message:
                return {'signature': ''}

            # Use Python's standard library — no external crypto dependency.
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding

            private_key = serialization.load_pem_private_key(
                private_key_pem.encode(),
                password=None,
            )
            signature = private_key.sign(
                message.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA512(),
            )
            return {'signature': base64.b64encode(signature).decode('ascii')}

        except Exception as exc:
            _logger.exception('QZ Tray sign error: %s', exc)
            return {'signature': '', 'error': str(exc)}
