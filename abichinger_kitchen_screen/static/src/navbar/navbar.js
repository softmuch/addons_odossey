/** @odoo-module */

import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
    get showReadyButton() {
        return this.pos.config.kitchen_ids && this.pos.config.kitchen_ids.length > 0
    },

    async onReadyButtonClick() {
        const kitchenId = this.pos.config.kitchen_ids[0]
        window.location = `/abichinger_kitchen_screen/app/?ks=${kitchenId}&select=ready`
    }
})