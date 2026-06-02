/** @odoo-module **/

import { PaymentScreenPaymentLines } from '@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines';
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenPaymentLines.prototype, {
    setup() {
        super.setup();
        for (const paymentLine of this.props.paymentLines) {
            // For split orders: keep ALL payment lines so they accumulate across rounds.
            // Each person's payment is preserved for correct pos.payment records in the backend.
            if (!paymentLine.pos_order_id?.is_split) {
                this.props.deleteLine(paymentLine.uuid);
            }
        }
    },
});
