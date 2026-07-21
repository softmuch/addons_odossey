import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";

function applyExpressPricelist(pos) {
    const order = pos.get_order();
    const config = pos.config;
    if (
        order?.is_express_checkout &&
        config.use_checkout_mode_pricelist &&
        config.express_checkout_pricelist_id
    ) {
        order.set_pricelist(config.express_checkout_pricelist_id);
    }
}

patch(Navbar.prototype, {
    async onExpressCheckout() {
        await super.onExpressCheckout();
        applyExpressPricelist(this.pos);
    },
});

patch(ReceiptScreen.prototype, {
    _addNewOrder() {
        super._addNewOrder(...arguments);
        applyExpressPricelist(this.pos);
    },
});
