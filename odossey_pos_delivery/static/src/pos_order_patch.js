import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(vals);
        this.is_delivery = this.is_delivery || false;
        this.delivery_record_id = false; // local only — not synced to server
    },
    init_from_JSON(json) {
        super.init_from_JSON(json);
        this.is_delivery = json.is_delivery || false;
    },
});
