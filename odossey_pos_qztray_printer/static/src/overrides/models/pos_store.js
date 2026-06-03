/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { QzTrayPrinter } from "@odossey_pos_qztray_printer/app/qztray_printer";

patch(PosStore.prototype, {
    /**
     * Hook into afterProcessServerData (called after all POS models are loaded)
     * to set the QzTrayPrinter as the RECEIPT printer (this.hardwareProxy.printer).
     * This mirrors the pattern used by pos_epson_printer.
     */
    async afterProcessServerData() {
        await super.afterProcessServerData(...arguments);
        const qzPrinterRecord = this.models["pos.printer"]
            ?.getAll()
            ?.find((p) => p.printer_type === "qztray");
        console.log('[QzTray] afterProcessServerData — printers:', this.models["pos.printer"]?.getAll()?.map(p => p.printer_type));
        if (qzPrinterRecord) {
            this.hardwareProxy.printer = new QzTrayPrinter(qzPrinterRecord.serialize());
            console.log('[QzTray] receipt printer set:', this.hardwareProxy.printer);
        } else {
            console.warn('[QzTray] no qztray printer found in pos.printer models');
        }
    },

    /**
     * Also hook create_printer so the same printer works as a
     * PREPARATION / KITCHEN printer (unwatched.printers path).
     */
    create_printer(config) {
        if (config.printer_type === "qztray") {
            return new QzTrayPrinter(config);
        }
        return super.create_printer(...arguments);
    },
});
