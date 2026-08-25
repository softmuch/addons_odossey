import { OrderDisplay } from "@point_of_sale/app/components/order_display/order_display";
import { patch } from "@web/core/utils/patch";
import { useState, useEffect  } from "@odoo/owl";

patch(OrderDisplay.prototype, {
    setup(){
        super.setup(...arguments)

        let order = this.order

        this.nf_state = useState({
            total_discount : order.get_nf_global_discount || 0
        })

        useEffect(() => {
            if (order && order.getOrderlines().length) {
                const globalDiscount = order.getOrderlines().reduce((total, line) => {
                    if (line.discount) {
                        return total + ((line.price_unit * line.qty * line.discount) / 100);
                    }
                    return total;
                }, 0);

                order.nf_global_discoount = globalDiscount;
                this.nf_state.total_discount = globalDiscount;
            } else {
                order.nf_global_discoount = 0;
                this.nf_state.total_discount = 0;
            }
        })
    },
    get formattedTotalDiscount() {
        const value = Number(this.nf_state.total_discount) || 0;
        return this.formatCurrency(value);
    }
})
