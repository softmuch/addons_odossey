import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { patch } from "@web/core/utils/patch";

patch(ActionpadWidget.prototype, {
    /**
     * Override submitOrder so that when is_order_printer is enabled, the "Order"
     * button submits the order WITHOUT printing (the "Order and print" button handles printing).
     *
     * We still call sendOrderInPreparationUpdateLastChange so that any other module
     * patching that method (e.g. abichinger_kitchen_screen) continues to work correctly.
     * Printing is inhibited by temporarily emptying printers_category_ids_set.
     */
    async submitOrder() {
        if (!this.uiState.clicked) {
            this.uiState.clicked = true;
            try {
                if (this.pos.config.is_order_printer) {
                    // Temporarily disable printing so kitchen screen and other patches
                    // that wrap sendOrderInPreparationUpdateLastChange still run,
                    // but the actual print step in sendOrderInPreparation is skipped.
                    const savedPrinters = this.pos.printers_category_ids_set;
                    this.pos.printers_category_ids_set = new Set();
                    try {
                        await this.pos.sendOrderInPreparationUpdateLastChange(this.currentOrder);
                    } finally {
                        this.pos.printers_category_ids_set = savedPrinters;
                    }
                } else {
                    // Original behavior: send to preparation (prints if printers are configured)
                    await this.pos.sendOrderInPreparationUpdateLastChange(this.currentOrder);
                }
            } finally {
                this.uiState.clicked = false;
            }
        }
    },

    /**
     * Submit the order AND send it to the order printer.
     * Only accessible when is_order_printer is enabled (button hidden otherwise).
     */
    async orderAndPrint() {
        if (!this.uiState.clicked) {
            this.uiState.clicked = true;
            try {
                await this.pos.sendOrderInPreparationUpdateLastChange(this.currentOrder);
            } finally {
                this.uiState.clicked = false;
            }
        }
    },
});
