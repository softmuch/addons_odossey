/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { SplitInfoDisplayPopup } from "./splitInfoDisplayPopup";

patch(TicketScreen.prototype, {
    setup() {
        super.setup();
    },

    onViewMore(clickedOrder) {
        const { is_split, split_done, to_split } = clickedOrder;
        if(is_split) {
            const splitAmt = clickedOrder.get_total_with_tax_split();
            var total_with_tax = clickedOrder.get_total_with_tax();
            if(clickedOrder.state == "paid") { 
                // const remainingPayment = total_with_tax - (splitAmt * split_done);
                this.dialog.add(SplitInfoDisplayPopup, {
                    body1: [[`Payment done`, parseFloat((splitAmt * split_done).toFixed(2)) + " " + this.pos.currency.symbol],[`Remaining payment`, 0 + " " + this.pos.currency.symbol]], 
                    body2: [[`Split done`, to_split], [`Remaining split`, 0], [`Total split`, to_split]], 
                    title: 'Split payment summary', 
                    confirmText: "Ok"});
            } else {
                const remainingPayment = total_with_tax - (splitAmt * split_done);
                this.dialog.add(SplitInfoDisplayPopup, {
                    body1: [[`Payment done`, parseFloat((splitAmt * split_done).toFixed(2)) + " " + this.pos.currency.symbol], [`Remaining payment`, remainingPayment.toFixed(2) + " " + this.pos.currency.symbol]], 
                    body2: [[`Split done`, split_done], [`Remaining split`, to_split - split_done], [`Total split`, to_split]], 
                    title: 'Split payment summary', 
                    confirmText: "Ok"});
            }
        }
    },
    getTotal(order) {
        return this.env.utils.formatCurrency(order.get_total_with_tax());
    }
})