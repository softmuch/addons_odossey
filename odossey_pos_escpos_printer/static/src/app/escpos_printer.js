/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";

/**
 * EscposPrinter — server-side TCP proxy for ESC/POS network printers.
 *
 * The browser sends the rendered receipt image to the Odoo server
 * (/pos/escpos_proxy/print).  The server converts it to ESC/POS raster
 * bytes and forwards them over a TCP socket to the printer on port 9100.
 *
 * This completely avoids the HTTPS → HTTP mixed-content / Chrome Private
 * Network Access restrictions that block direct browser-to-printer calls.
 */
export class EscposPrinter extends BasePrinter {
    setup({ printerId }) {
        this.printerId = printerId;
    }

    /**
     * Send the receipt image (base64 JPEG, produced by BasePrinter.processCanvas)
     * to the Odoo proxy endpoint and return the result.
     *
     * @param {string} image  Base64-encoded JPEG string
     * @returns {{ successful: boolean }}
     */
    async sendPrintingJob(image) {
        try {
            const response = await fetch('/pos/escpos_proxy/print', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    id: Date.now(),
                    params: {
                        printer_id: this.printerId,
                        image_b64: image,
                    },
                }),
            });
            const json = await response.json();
            if (json.result?.success) {
                return { successful: true };
            }
            const errorMsg = json.result?.error || json.error?.message || 'Unknown error';
            return {
                successful: false,
                message: { title: 'Printer error', body: errorMsg },
            };
        } catch (err) {
            return {
                successful: false,
                message: { title: 'Network error', body: String(err) },
            };
        }
    }

    /** Send a cash-drawer open pulse through the printer. */
    async openCashbox() {
        try {
            await fetch('/pos/escpos_proxy/cashbox', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    id: Date.now(),
                    params: { printer_id: this.printerId },
                }),
            });
        } catch (_) {
            // Cash drawer errors are non-fatal
        }
    }
}
