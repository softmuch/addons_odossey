/** @odoo-module **/

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
    isSelected() {
        if(this.is_completed_split_payment){
            return false
        }else{
            return this.pos_order_id?.uiState?.selected_paymentline_uuid === this.uuid;
        }
    },
    // True when this line belongs to an already-validated split round.
    // Used by PaymentScreenPaymentLines to preserve it instead of deleting it.
    get is_completed_split_payment() {
        const order = this.pos_order_id;
        const uuids = order?.completedSplitPaymentUuids;
        if (uuids) {
            return uuids.has(this.uuid);
        }
        // After a page reload the in-memory set is lost: a line already saved on the
        // server (numeric id) of a partially paid split order belongs to a completed round,
        // because payment lines are only synced together with splitDone().
        return !!(order?.is_split && order.split_done > 0 && typeof this.id === "number");
    },
});
