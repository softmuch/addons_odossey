import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    /**
     * When is_order_printer is enabled, suppress printing on order cancellation.
     * Printing is handled exclusively by the "Print" button.
     */
    async checkPreparationStateAndSentOrderInPreparation(order, cancelled = false) {
        if (cancelled && this.config.is_order_printer) {
            const savedPrinters = this.printers_category_ids_set;
            this.printers_category_ids_set = new Set();
            try {
                return await super.checkPreparationStateAndSentOrderInPreparation(order, cancelled);
            } finally {
                this.printers_category_ids_set = savedPrinters;
            }
        }
        return super.checkPreparationStateAndSentOrderInPreparation(order, cancelled);
    },
});
