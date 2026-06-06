import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    // Run after all models are loaded AND after odossey_pos_qztray_printer
    // has already set this.hardwareProxy.printer via its afterProcessServerData patch.
    async afterProcessServerData() {
        await super.afterProcessServerData(...arguments);
        if (this.config.printer_assignment_mode === "per_user") {
            this._applyUserPrinterFilter();
        }
    },

    _applyUserPrinterFilter() {
        const prepMap = JSON.parse(this.config.user_printer_map || "{}");
        const receiptMap = JSON.parse(this.config.user_receipt_printer_map || "{}");

        const userId = this.user.id;
        const key = String(userId);

        const assignedPrepId = prepMap[key];
        const assignedReceiptId = receiptMap[key];

        // --- Preparation printers ---
        if (assignedPrepId) {
            this.unwatched.printers = this.unwatched.printers.filter(
                (p) => p.config.id === assignedPrepId
            );
        } else {
            this.unwatched.printers = [];
        }

        this.printers_category_ids_set = new Set();
        for (const printer of this.unwatched.printers) {
            for (const id of printer.config.product_categories_ids) {
                this.printers_category_ids_set.add(id);
            }
        }
        this.config.iface_printers = !!this.unwatched.printers.length;

        // --- Receipt printer (checkout) ---
        // Runs after qztray_printer's afterProcessServerData, so we overwrite
        // hardwareProxy.printer only when the user has an explicit assignment.
        if (assignedReceiptId) {
            const printerRecord = this.models["pos.printer"]
                ?.getAll()
                ?.find((p) => p.id === assignedReceiptId);
            if (printerRecord) {
                const config = printerRecord.serialize();
                const receiptPrinter = this.create_printer(config);
                if (receiptPrinter) {
                    receiptPrinter.config = config;
                    this.hardwareProxy.printer = receiptPrinter;
                }
            }
        }
    },
});
