import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
    get isExpressCheckout() {
        if (this.pos.mainScreen?.component?.name === 'DeliveryScreen') return false;
        return !!this.pos.get_order()?.is_express_checkout;
    },

    // Single getter for topheader bar color — replaces delivery module's t-att-class (last extension wins).
    // Must handle both states or the delivery orange disappears.
    get navbarBarClass() {
        const order = this.pos.get_order();
        const screenName = this.pos.mainScreen?.component?.name;
        if (order?.is_delivery || screenName === 'DeliveryScreen') return 'bg-delivery-order border-0';
        if (order?.is_express_checkout) return 'express-checkout-active';
        return '';
    },

    async onExpressCheckout() {
        await this.pos.syncAllOrders();
        const newOrder = this.pos.add_new_order();
        newOrder.is_express_checkout = true;
        this.pos.selectedTable = null;
        this.pos.set_order(newOrder);
        this.pos.showScreen("ProductScreen");
    },
});
