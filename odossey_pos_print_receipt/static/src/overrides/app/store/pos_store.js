import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";


patch(PosStore.prototype, {
    async printReceipt({ basic = false, order = this.get_order() } = {}) {
        const result = await super.printReceipt(...arguments);
        if (Number.isInteger(order.id)) {
            await this.data.write("pos.order", [order.id], { nb_print: 0 });
        }
        return result;
    },
});
