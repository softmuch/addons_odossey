/** @odoo-module **/

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
    isSelected() { 
        if(this.pos_order_id.is_split){
            return false
        }else{
            return this.pos_order_id?.uiState?.selected_paymentline_uuid === this.uuid;
        }
    }
});
