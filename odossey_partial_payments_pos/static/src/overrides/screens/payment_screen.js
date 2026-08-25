/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { useAsyncLockedMethod } from "@point_of_sale/app/hooks/hooks";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.validatePartialOrder = useAsyncLockedMethod(this.validatePartialOrder);
    },

    /**
     * Deliberate, explicit "partial payment" validation: some payment has
     * been applied but not the full amount due. Unlike `validateOrder`,
     * this is only exposed through its own dedicated button in the UI (see
     * payment_screen.xml) so a cashier can never trigger it by accident.
     */
    async validatePartialOrder() {
        const validation = new OrderPaymentValidation({
            pos: this.pos,
            orderUuid: this.currentOrder.uuid,
        });
        // Set after construction: the base constructor destructures its
        // argument object (`{ pos, orderUuid, fastPaymentMethod }`) and
        // would drop an `allowPartial` key passed in there.
        validation.allowPartial = true;
        await validation.validateOrder(false);
    },
});
