import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";

// New orders default to Floor mode pricelist; onExpressCheckout/_addNewOrder
// (express_checkout_pricelist.js) override to the Express pricelist right after.
patch(PosStore.prototype, {
    createNewOrder(data = {}) {
        const order = super.createNewOrder(data);
        const config = this.config;
        if (config.use_checkout_mode_pricelist && config.floor_checkout_pricelist_id) {
            order.set_pricelist(config.floor_checkout_pricelist_id);
        }
        return order;
    },
});
