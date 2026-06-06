import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        if (this.config.printer_assignment_mode === "per_user") {
            this._applyUserPrinterFilter();
        }
    },

    _applyUserPrinterFilter() {
        const userPrinterMap = JSON.parse(this.config.user_printer_map || "{}");
        // Use the current browser session user id (most reliable across scenarios)
        const userId =
            this.session.user_id?.id ??
            this.session.user_id ??
            odoo?.session_info?.uid;

        const assignedPrinterId = userPrinterMap[String(userId)];

        if (assignedPrinterId) {
            this.unwatched.printers = this.unwatched.printers.filter(
                (p) => p.config.id === assignedPrinterId
            );
        } else {
            // No printer assigned to this user — print nothing
            this.unwatched.printers = [];
        }

        // Rebuild the printer categories set from the filtered printers
        this.printers_category_ids_set = new Set();
        for (const printer of this.unwatched.printers) {
            for (const id of printer.config.product_categories_ids) {
                this.printers_category_ids_set.add(id);
            }
        }
        this.config.iface_printers = !!this.unwatched.printers.length;
    },
});
