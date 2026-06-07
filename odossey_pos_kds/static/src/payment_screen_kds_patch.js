import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { changesToOrder } from "@point_of_sale/app/models/utils/order_change";
import { KitchenWarningDialog } from "@odossey_pos_kds/kitchen_warning_dialog";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this._kdsDialog = useService("dialog");
    },

    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const { new: kdsNew, cancelled: kdsCancelled, noteUpdated: kdsNoteUpdated } =
            changesToOrder(order, false, new Set(), false);
        const hasUnsentChanges =
            kdsNew.length > 0 || kdsCancelled.length > 0 || kdsNoteUpdated.length > 0;

        if (hasUnsentChanges) {
            const choice = await new Promise((resolve) => {
                let settled = false;
                const once = (val) => { if (!settled) { settled = true; resolve(val); } };
                this._kdsDialog.add(
                    KitchenWarningDialog,
                    {
                        onProceed: () => once("proceed"),
                        onOrder:   () => once("order"),
                        onCancel:  () => once("cancel"),
                    },
                    { onClose: () => once("cancel") }
                );
            });

            if (choice === "cancel") {
                this.pos.showScreen("ProductScreen");
                return;
            }
            if (choice === "order") {
                try {
                    await this.pos.sendToKdsOnly(order);
                } catch (e) {
                    console.error("KDS send failed:", e);
                }
                // Fall through to payment after sending to KDS
            }
            // "proceed": fall through to normal validation
        }

        await super.validateOrder(isForceValidate);
    },
});
