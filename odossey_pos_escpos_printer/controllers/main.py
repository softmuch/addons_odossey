import base64
import io
import logging
import socket

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# ESC/POS command constants
ESC_INIT      = b'\x1b\x40'          # ESC @ — initialize printer
CUT_PARTIAL   = b'\x1d\x56\x01'      # GS V 1 — partial cut with feed
CASHBOX_PULSE = b'\x1b\x70\x00\x32\xfa'  # ESC p 0 50 250 — drawer 1 open


def _image_to_escpos_bytes(image_b64: str, paper_width_mm: int = 80) -> bytes:
    """
    Convert a base64 JPEG receipt image to raw ESC/POS raster bytes.

    Uses the GS v 0 (raster image) command which is supported by virtually
    all modern thermal printers including 3nStar, Epson TM-*, Star TSP100,
    Bixolon, etc.  No external dependencies — only PIL/Pillow which is
    already bundled with Odoo.
    """
    from PIL import Image  # PIL is included in Odoo's dependencies

    # Decode base64 → PIL Image
    raw_bytes = base64.b64decode(image_b64)
    img = Image.open(io.BytesIO(raw_bytes))

    # Target width in pixels (203 dpi is the standard for 80mm thermal paper)
    DPI = 203
    target_width = round(paper_width_mm / 25.4 * DPI)
    # Cap at multiples of 8 so byte packing is clean
    target_width = (target_width // 8) * 8

    # Resize proportionally
    orig_w, orig_h = img.size
    target_height = round(orig_h * target_width / orig_w)

    img = img.resize((target_width, target_height), Image.LANCZOS)

    # Convert to grayscale then 1-bit B&W using a threshold of 128
    img = img.convert('L')
    img = img.point(lambda px: 0 if px < 128 else 255)
    img = img.convert('1')

    width_bytes = target_width // 8

    # GS v 0 header: 0x1D 0x76 0x30 m xL xH yL yH
    header = bytearray([
        0x1d, 0x76, 0x30, 0x00,                          # GS v 0, normal size
        width_bytes & 0xFF, (width_bytes >> 8) & 0xFF,   # xL xH
        target_height & 0xFF, (target_height >> 8) & 0xFF,  # yL yH
    ])

    # Pack pixel rows into bytes (MSB first, black pixel = 1)
    pixel_data = bytearray()
    for y in range(target_height):
        for bx in range(width_bytes):
            byte = 0
            for bit in range(8):
                x = bx * 8 + bit
                if x < target_width and not img.getpixel((x, y)):
                    byte |= (0x80 >> bit)
            pixel_data.append(byte)

    return ESC_INIT + bytes(header) + bytes(pixel_data) + CUT_PARTIAL


def _send_tcp(ip: str, port: int, data: bytes, timeout: float = 5.0) -> None:
    """Open a TCP socket, send *data*, then close."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.sendall(data)
    finally:
        sock.close()


class EscposProxyController(http.Controller):

    @http.route(
        '/pos/escpos_proxy/print',
        type='json',
        auth='user',
        csrf=False,
        methods=['POST'],
    )
    def print_receipt(self, printer_id, image_b64, **kwargs):
        """
        Receive a base64 JPEG receipt from the POS browser and send it to
        the ESC/POS printer over TCP.

        Called by EscposPrinter.sendPrintingJob() in the JS layer.
        """
        try:
            printer = request.env['pos.printer'].sudo().browse(int(printer_id))
            if not printer.exists() or printer.printer_type != 'escpos_network':
                return {'success': False, 'error': 'Printer not found or wrong type'}

            escpos_data = _image_to_escpos_bytes(
                image_b64,
                paper_width_mm=printer.paper_width_mm or 80,
            )
            _send_tcp(printer.escpos_ip, printer.escpos_port or 9100, escpos_data)
            return {'success': True}

        except Exception as exc:
            _logger.exception('ESC/POS proxy print error for printer %s', printer_id)
            return {'success': False, 'error': str(exc)}

    @http.route(
        '/pos/escpos_proxy/cashbox',
        type='json',
        auth='user',
        csrf=False,
        methods=['POST'],
    )
    def open_cashbox(self, printer_id, **kwargs):
        """Send cash-drawer open pulse via the ESC/POS printer."""
        try:
            printer = request.env['pos.printer'].sudo().browse(int(printer_id))
            if not printer.exists() or printer.printer_type != 'escpos_network':
                return {'success': False, 'error': 'Printer not found or wrong type'}

            _send_tcp(
                printer.escpos_ip,
                printer.escpos_port or 9100,
                ESC_INIT + CASHBOX_PULSE,
            )
            return {'success': True}

        except Exception as exc:
            _logger.exception('ESC/POS cashbox error for printer %s', printer_id)
            return {'success': False, 'error': str(exc)}
