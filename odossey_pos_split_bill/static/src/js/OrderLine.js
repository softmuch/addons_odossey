import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

patch(Orderline.prototype, {
    setup(){
        super.setup(...arguments);
        this.pos = usePos();
        this.currentorder = this.pos.get_order();
    }, 
});

patch(PosOrderline.prototype, {
    setup(){
        super.setup(...arguments); 
        this.currentorder = this.order_id;
    },
    get_price_with_tax() { 
        if(this.currentorder.is_split){
            return this.get_all_prices().priceWithTax / this.currentorder.to_split;
        }
        return this.get_all_prices().priceWithTax;
    },
    get_price_without_tax() {
        if(this.currentorder.is_split){
            return this.get_all_prices().priceWithTax / this.currentorder.to_split;
        }
        return this.get_all_prices().priceWithoutTax;
    }
});