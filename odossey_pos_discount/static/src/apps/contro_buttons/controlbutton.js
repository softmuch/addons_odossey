
/** @odoo-module */
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { ask, makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";
import { parseFloat } from "@web/views/fields/parsers";

patch(NumberPopup, {
    props: {
        ...NumberPopup.props,
        isInputSelected: { type: Boolean, optional: true },
        is_custom_discount: { type: Boolean, optional: true },
    },
});

patch(ControlButtons.prototype, {
    async GlobalDiscount() {
        var order = this.pos.getOrder();
        if (order) {
            const payload = await  await makeAwaitable(this.dialog, NumberPopup, {
                title: _t("Discount"),
                startingValue: 1,
                isInputSelected: true,
                is_custom_discount: true,
            });
            console.log('payload', payload);

            if (payload) {
                if (payload && payload.discount_type == "price") {
                    order.set_nf_global_discount(0.00);
                    const orderTotal  = order.priceIncl;
                    const discountamount = payload.amount;
                    var percentage = (discountamount / orderTotal ) * 100;
                    [...order.getOrderlines()].map(async (line) => {
                        await line.setDiscount(percentage)
                    })

                } else {
                    const amount = typeof payload === 'string' ? parseFloat(payload) : payload
                    const val = Math.max(0, Math.min(100, amount));

                    const Totalprice = order.priceIncl;
                    var percentage = (Totalprice * val) / 100;
                    var lineDiscountPercentage = (percentage / Totalprice) * 100;
                    [...order.getOrderlines()].map(async (line) => {
                        await line.setDiscount(lineDiscountPercentage)
                    })
                    order.set_nf_global_discount(percentage);
                }
            }
        } else {
            this.popup.add(ErrorPopup, {
                title: _t("Discount!"),
                body: _t(
                    "Please Add Product in Cart !"
                ),
            });
        }
    },
    async removeDiscount() {
        var order = this.pos.getOrder()
        if (order){
            [...order.getOrderlines()].map(async (line) => {
                await line.setDiscount(0)
            })
            order.set_nf_global_discount(0);
        }
    }
})