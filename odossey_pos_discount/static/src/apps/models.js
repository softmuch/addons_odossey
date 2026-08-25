
/** @odoo-module */
import { patch } from "@web/core/utils/patch";

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

patch(PosOrder.prototype, {
    get get_nf_global_discount(){
        return this.nf_global_discoount || 0
    },
    set_nf_global_discount(discount){
        this.nf_global_discoount = discount
    }
})

patch(PosOrderline.prototype,{
    // set_discount(discount) {
    //     // var percentage = ((this.price_unit * this.qty) * discount) / 100;
    //     // this.order_id.set_nf_global_discount(percentage);
    //     super.set_discount(...arguments)
    // },
    setQuantity(quantity, keep_price) {
        var res = super.setQuantity(...arguments)
        // var percentage = ((this.price_unit * this.qty) * this.discount) / 100;
        // this.order_id.set_nf_global_discount(percentage);
        return res
    }
})
