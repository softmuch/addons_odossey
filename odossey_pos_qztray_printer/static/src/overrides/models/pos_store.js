/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { QzTrayPrinter } from "@odossey_pos_qztray_printer/app/qztray_printer";

patch(PosStore.prototype, {
    create_printer(config) {
        if (config.printer_type === 'qztray') {
            return new QzTrayPrinter(config);
        }
        return super.create_printer(...arguments);
    },
});
