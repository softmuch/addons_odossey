import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";
import { patch } from "@web/core/utils/patch";
import { useState, useEffect  } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

patch(OrderWidget, {
    props: {
        ...OrderWidget.props,
        total_discount: { type: String, optional: true },
    },
});

patch(OrderWidget.prototype, {
    setup(){
        super.setup(...arguments)
        this.pos = usePos()

        let order = this.pos.get_order()

        this.nf_state = useState({
            total_discount : (order && order.get_nf_global_discount) || 0
        })

        useEffect(() => {
            if (order && order.get_orderlines().length) {
                const globalDiscount = order.get_orderlines().reduce((total, line) => {
                    if (line.discount) {
                        return total + ((line.price_unit * line.qty * line.discount) / 100);
                    }
                    return total;
                }, 0);

                order.nf_global_discoount = globalDiscount;
                this.nf_state.total_discount = globalDiscount;
            } else if (order) {
                order.nf_global_discoount = 0;
                this.nf_state.total_discount = 0;
            }
        })
    },
    get formattedTotalDiscount() {
        const value = Number(this.nf_state.total_discount) || 0;
        return this.pos.env.utils.formatCurrency(value);
    }
})