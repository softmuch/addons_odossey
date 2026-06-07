import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";

patch(ReceiptScreen.prototype, {
    get nextScreen() {
        if (this.currentOrder?.is_delivery) {
            return { name: "DeliveryScreen" };
        }
        return super.nextScreen;
    },
});
