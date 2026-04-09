/** @odoo-module **/
 
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
const { onWillUpdateProps } = owl;

patch(OrderReceipt.prototype,{
    setup(){
        super.setup(); 
        // this.currentorder = this.pos.get_order();
    },
})   
