/** @odoo-module **/

import { PaymentScreenPaymentLines } from '@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines';
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenPaymentLines.prototype, {
    setup() {
        super.setup();
        for (const paymentLine of this.props.paymentLines) {
            // For split orders: keep payment lines that are already synced to the
            // server (real integer ID). They represent previous persons' payments
            // and must accumulate in pos_payment for correct accounting.
            // Only delete un-synced (new, local-only) lines.
            const isSyncedSplitPayment =
                paymentLine.pos_order_id?.is_split &&
                Number.isInteger(paymentLine.id) &&
                paymentLine.id > 0;
            if (!isSyncedSplitPayment) {
                this.props.deleteLine(paymentLine.uuid);
            }
        }
    },
});
