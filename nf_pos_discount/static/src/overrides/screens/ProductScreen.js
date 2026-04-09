/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { parseFloat } from "@web/views/fields/parsers";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { ask, makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";


patch(ProductScreen.prototype, {
    async onNumpadClick(buttonValue) {
        super.onNumpadClick(...arguments);
        const mode = buttonValue
        console.log(this);
        
        if (
            mode === "discount" &&
            this.pos.config.nf_enbale_price_discount
        ) {
            let order = this.pos.get_order();
            if (order.get_selected_orderline()) {
                const payload = await  await makeAwaitable(this.dialog, NumberPopup, {
                        title: _t("Discount"),
                        startingValue: order.get_selected_orderline().discount ? order.get_selected_orderline().discount :  1,
                        isInputSelected: true,
                        is_custom_discount: true,
                    }
                );
                
                if (payload) {
                    console.log('payload',payload);
                    
                    if (payload && payload.discount_type == "price") {
                        const Totalprice = order.get_selected_orderline().get_display_price();
                        const discountamount = payload.amount;
                        var percentage = (discountamount / Totalprice) * 100;
                        percentage = percentage
                        // let old_discount_amount = order.get_nf_global_discount()
                        order.set_nf_global_discount(discountamount);
                        order.get_selected_orderline().set_discount(percentage);
                    } else {
                        await order.get_selected_orderline().set_discount(payload);
                    }
                }
            }
        }
    },
});