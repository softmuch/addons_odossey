/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";

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
        if (this.certificate) {
            // Signed mode: certificate stored in Odoo, private key signs server-side.
            qz.security.setCertificatePromise(() => Promise.resolve(this.certificate));
            qz.security.setSignatureAlgorithm('SHA512');
            qz.security.setSignaturePromise((toSign) => {
                return fetch('/pos/qztray/sign', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: '2.0', method: 'call', id: 1,
                        params: { message: toSign },
                    }),
                }).then((r) => r.json()).then((j) => j.result?.signature || '');
            });
        } else {
            // Unsigned mode: QZ Tray shows a one-time trust dialog.
            qz.security.setCertificatePromise(() => Promise.resolve(null));
            qz.security.setSignaturePromise(() => Promise.resolve(null));
        }
    }

    // ── WebSocket connection ────────────────────────────────────────────────

    async _connect() {
        if (typeof qz === 'undefined') {
            throw new Error('qz-tray.js not loaded');
        }
        if (qz.websocket.isActive()) return;
        // Dedup concurrent _connect() calls
        if (!this._connecting) {
            this._setupSigning();
            this._connecting = qz.websocket.connect({
                host: this.host,
                port: { secure: [this.port] },
                usingSecure: true,
                retries: 1,
                delay: 0.5,
            }).catch(() =>
                // Fallback: try insecure (port +1: 8181→8182, 8282→8283 …)
                qz.websocket.connect({
                    host: this.host,
                    port: { insecure: [this.port + 1] },
                    usingSecure: false,
                    retries: 1,
                    delay: 0.5,
                })
            ).finally(() => {
                this._connecting = null;
            });
        }
        return this._connecting;
    }

    // ── Printer config factory ──────────────────────────────────────────────

    async _makeConfig() {
        if (this.mode === 'socket') {
            // Raw TCP socket — no OS driver needed
            return qz.configs.create({
                host: this.socketIp,
                port: this.socketPort,
            });
        }

        // OS printer mode
        let printerTarget;
        if (this.printerName) {
            // find() returns the exact name (or throws if not found)
            printerTarget = await qz.printers.find(this.printerName);
        } else {
            // Use the OS default printer
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

            await qz.print(config, data);
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
            await qz.print(config, [{ flavor: 'base64', data: b64 }]);
        } catch (_) {
            // Cash drawer errors are non-fatal
        }
    }
}
