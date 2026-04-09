import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    orderExportForPrinting(order) {
        const headerData = this.getReceiptHeaderData(order);
        const baseUrl = this.session._base_url;
        if (order.is_split) {
            return order.export_for_printing_split(baseUrl, headerData);
        }
        return order.export_for_printing(baseUrl, headerData);
    }
});