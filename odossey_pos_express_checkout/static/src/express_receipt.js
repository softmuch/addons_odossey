import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";
import { getOrCreateExpressOrder } from "./express_checkout_utils";

patch(ReceiptScreen.prototype, {
    // pos_restaurant overrides _addNewOrder to do nothing (avoids creating a new order on FloorScreen).
    // We restore that behavior for express checkout: create a new express checkout order directly.
    _addNewOrder() {
        if (this.currentOrder?.is_express_checkout) {
            const order = getOrCreateExpressOrder(this.pos);
            this.pos.set_order(order);
            return;
        }
        return super._addNewOrder(...arguments);
    },

    // pos_restaurant overrides nextScreen to return FloorScreen.
    // For express checkout we stay on ProductScreen instead.
    get nextScreen() {
        if (this.currentOrder?.is_express_checkout) {
            return { name: "ProductScreen" };
        }
        return super.nextScreen;
    },
});
