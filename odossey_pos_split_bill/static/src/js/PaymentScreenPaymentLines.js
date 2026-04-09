/** @odoo-module **/

import { PaymentScreenPaymentLines } from '@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines';
import { patch } from "@web/core/utils/patch"; 

patch(PaymentScreenPaymentLines.prototype,{
    setup(){
        super.setup();
        for (const paymentLine of this.props.paymentLines) {
            this.props.deleteLine(paymentLine.uuid);
        }
    },
});