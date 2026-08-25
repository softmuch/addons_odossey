/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { parseFloat } from "@web/views/fields/parsers";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { ask, makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
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
            let order = this.pos.getOrder();
            if (order.getSelectedOrderline()) {
                const payload = await  await makeAwaitable(this.dialog, NumberPopup, {
                        title: _t("Discount"),
                        startingValue: order.getSelectedOrderline().discount ? order.getSelectedOrderline().discount :  1,
                        isInputSelected: true,
                        is_custom_discount: true,
                    }
                );

                if (payload) {
                    console.log('payload',payload);

                    if (payload && payload.discount_type == "price") {
                        const Totalprice = order.getSelectedOrderline().displayPrice;
                        const discountamount = payload.amount;
                        var percentage = (discountamount / Totalprice) * 100;
                        percentage = percentage
                        // let old_discount_amount = order.get_nf_global_discount()
                        order.set_nf_global_discount(discountamount);
                        order.getSelectedOrderline().setDiscount(percentage);
                    } else {
                        await order.getSelectedOrderline().setDiscount(payload);
                    }
                }
            }
        }
    },
});