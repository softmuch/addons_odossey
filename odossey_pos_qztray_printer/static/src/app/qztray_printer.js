/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";
import { loadJS } from "@web/core/assets";

const QZ_TRAY_JS_URL = '/odossey_pos_qztray_printer/static/lib/qz-tray.js';
let _qzLoadPromise = null;

async function ensureQzLoaded() {
    if (typeof window.qz !== 'undefined') return;
    if (!_qzLoadPromise) {
        _qzLoadPromise = loadJS(QZ_TRAY_JS_URL);
    }
    await _qzLoadPromise;
}

// ---------------------------------------------------------------------------
// ESC/POS raster image encoder (used in socket mode only)
// Converts a base64 JPEG to GS v 0 raster bytes in the browser via Canvas API.
// ---------------------------------------------------------------------------
async function imageToEscPosBase64(base64Jpeg, paperWidthMm = 80) {
    const DPI = 203; // standard thermal printer resolution
    const targetWidth = Math.floor((paperWidthMm / 25.4) * DPI / 8) * 8; // round to byte boundary

    const img = await new Promise((resolve, reject) => {
        const i = new Image();
        i.onload = () => resolve(i);
        i.onerror = reject;
        i.src = 'data:image/jpeg;base64,' + base64Jpeg;
    });

    const targetHeight = Math.round(img.height * (targetWidth / img.width));
    const canvas = document.createElement('canvas');
    canvas.width = targetWidth;
    canvas.height = targetHeight;
    const ctx = canvas.getContext('2d');

    // White background + draw image
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, targetWidth, targetHeight);
    ctx.drawImage(img, 0, 0, targetWidth, targetHeight);

    const { data: pixels } = ctx.getImageData(0, 0, targetWidth, targetHeight);
    const widthBytes = targetWidth / 8;

    // GS v 0 header
    const header = [
        0x1D, 0x76, 0x30, 0x00,
        widthBytes & 0xFF, (widthBytes >> 8) & 0xFF,
        targetHeight & 0xFF, (targetHeight >> 8) & 0xFF,
    ];

    // Pack pixels — black (luminance < 128) → bit 1, MSB first
    const pixelData = [];
    for (let y = 0; y < targetHeight; y++) {
        for (let bx = 0; bx < widthBytes; bx++) {
            let byte = 0;
            for (let bit = 0; bit < 8; bit++) {
                const x = bx * 8 + bit;
                const idx = (y * targetWidth + x) * 4;
                const r = pixels[idx], g = pixels[idx + 1], b = pixels[idx + 2];
                if (0.299 * r + 0.587 * g + 0.114 * b < 128) {
                    byte |= (0x80 >> bit);
                }
            }
            pixelData.push(byte);
        }
    }

    const ESC_INIT = [0x1B, 0x40];
    const CUT     = [0x1D, 0x56, 0x01]; // partial cut
    const all = new Uint8Array([...ESC_INIT, ...header, ...pixelData, ...CUT]);

    // Convert to base64 for QZ Tray flavor:'base64'
    let binary = '';
    for (let i = 0; i < all.length; i++) {
        binary += String.fromCharCode(all[i]);
    }
    return btoa(binary);
}

// ---------------------------------------------------------------------------
// QzTrayPrinter — sends receipts via the local QZ Tray desktop app.
//
// Two modes:
//   os     → QZ Tray uses the OS printer driver (printer installed in the OS).
//            Image sent as type:'pixel' format:'image' — QZ Tray scales & renders.
//   socket → QZ Tray opens a raw TCP socket to the printer (IP:port).
//            Image converted to ESC/POS raster bytes in the browser, sent as raw.
// ---------------------------------------------------------------------------
export class QzTrayPrinter extends BasePrinter {
    setup(config) {
        super.setup();
        this.host          = config.qztray_host || 'localhost';
        this.port          = config.qztray_port || 8181;
        this.mode          = config.qztray_mode || 'os';
        this.printerName   = config.qztray_printer_name || '';
        this.socketIp      = config.qztray_socket_ip || '';
        this.socketPort    = config.qztray_socket_port || 9100;
        this.paperWidthMm  = config.qztray_paper_width_mm || 80;
        this.certificate   = config.qztray_certificate || null;

        this._connecting = null; // in-flight connect promise (dedup)
    }

    // ── Certificate / signing ───────────────────────────────────────────────

    _setupSigning() {
        const qz = window.qz;
        if (this.certificate) {
            // Signed mode: certificate + server-side signing
            qz.security.setCertificatePromise((resolve) => resolve(this.certificate));
            qz.security.setSignatureAlgorithm('SHA512');
            qz.security.setSignaturePromise((toSign) => (resolve, reject) => {
                fetch('/pos/qztray/sign', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: '2.0', method: 'call', id: 1,
                        params: { message: toSign },
                    }),
                }).then((r) => r.json()).then((j) => resolve(j.result?.signature || '')).catch(reject);
            });
        } else {
            // Unsigned mode: QZ Tray shows one-time trust dialog
            // setCertificatePromise must resolve with null (not reject)
            qz.security.setCertificatePromise((resolve) => resolve(null));
            // setSignaturePromise factory must return a resolver function
            qz.security.setSignaturePromise(() => (resolve) => resolve(null));
        }
    }

    // ── WebSocket connection ────────────────────────────────────────────────

    async _connect() {
        await ensureQzLoaded();
        if (window.qz.websocket.isActive()) return;
        // Dedup concurrent _connect() calls
        if (!this._connecting) {
            this._setupSigning();
            const qz = window.qz;
            // Try both secure and insecure in one connect call.
            // QZ Tray cycles through all ports automatically.
            // Start insecure (usingSecure: false) to avoid the
            // wss→ws fallback race condition in qz-tray.js 2.2.x.
            this._connecting = qz.websocket.connect({
                host: this.host,
                port: {
                    secure: [this.port],
                    insecure: [this.port + 1],
                },
                usingSecure: false,
                retries: 0,
                delay: 0,
            }).finally(() => {
                this._connecting = null;
            });
        }
        return this._connecting;
    }

    // ── Printer config factory ──────────────────────────────────────────────

    async _makeConfig() {
        const qz = window.qz;
        if (this.mode === 'socket') {
            return qz.configs.create({
                host: this.socketIp,
                port: this.socketPort,
            });
        }

        let printerTarget;
        if (this.printerName) {
            printerTarget = await qz.printers.find(this.printerName);
        } else {
            printerTarget = await qz.printers.getDefault();
        }
        return qz.configs.create(printerTarget, {
            colorType: 'grayscale',
            scaleContent: false,
        });
    }

    // ── BasePrinter contract ────────────────────────────────────────────────

    async sendPrintingJob(image) {
        // `image` = base64 JPEG string from BasePrinter.processCanvas()
        try {
            await this._connect();
            const config = await this._makeConfig();

            let data;
            if (this.mode === 'socket') {
                // Convert image to ESC/POS raster bytes in the browser
                const escposB64 = await imageToEscPosBase64(image, this.paperWidthMm);
                data = [{ flavor: 'base64', data: escposB64 }];
            } else {
                // OS printer: QZ Tray renders the image using the OS driver
                data = [{
                    type: 'pixel',
                    format: 'image',
                    flavor: 'base64',
                    data: image,
                    options: { language: 'ESCPOS' },
                }];
            }

            await window.qz.print(config, data);
            return { successful: true };

        } catch (err) {
            return {
                successful: false,
                message: {
                    title: 'QZ Tray Error',
                    body: String(err),
                },
            };
        }
    }

    async openCashbox() {
        try {
            await this._connect();
            const config = await this._makeConfig();
            // ESC p 0 50 250 — cash drawer pulse on connector 1
            const CASHBOX = [0x1B, 0x70, 0x00, 0x32, 0xFA];
            const b64 = btoa(CASHBOX.map((b) => String.fromCharCode(b)).join(''));
            await window.qz.print(config, [{ flavor: 'base64', data: b64 }]);
        } catch (_) {
            // Cash drawer errors are non-fatal
        }
    }
}
