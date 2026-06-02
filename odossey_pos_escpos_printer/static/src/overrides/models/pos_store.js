/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { EscposPrinter } from "@odossey_pos_escpos_printer/app/escpos_printer";

patch(PosStore.prototype, {
    /**
     * Override create_printer to instantiate EscposPrinter when
     * the printer type is 'escpos_network'.
     */
    create_printer(config) {
        if (config.printer_type === 'escpos_network') {
            return new EscposPrinter({ printerId: config.id });
        }
        return super.create_printer(...arguments);
    },
});
