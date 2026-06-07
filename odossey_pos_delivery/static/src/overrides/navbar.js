import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
    openDeliveryScreen() {
        this.pos.showScreen("DeliveryScreen");
    },

    get isDeliveryScreen() {
        return this.pos.mainScreen.component?.name === "DeliveryScreen";
    },
});
