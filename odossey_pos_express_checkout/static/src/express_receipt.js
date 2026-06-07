import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";

patch(ReceiptScreen.prototype, {
    // pos_restaurant overrides _addNewOrder to do nothing (avoids creating a new order on FloorScreen).
    // We restore that behavior for express checkout: create a new express checkout order directly.
    _addNewOrder() {
        if (this.currentOrder?.is_express_checkout) {
            const newOrder = this.pos.add_new_order();
            newOrder.is_express_checkout = true;
            this.pos.selectedTable = null;
            this.pos.set_order(newOrder);
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
