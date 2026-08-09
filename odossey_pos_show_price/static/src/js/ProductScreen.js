import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";

patch(ProductScreen.prototype, {
    getProductPrice(product) {
        const order = this.pos.getOrder();
        const pricelist = order?.pricelist_id || this.pos.config.pricelist_id || false;
        const taxDetails = product.getTaxDetails({ overridedValues: { pricelist } });
        const price =
            this.pos.config.iface_tax_included === "total"
                ? taxDetails.total_included
                : taxDetails.total_excluded;
        const formattedUnitPrice = this.env.utils.formatCurrency(price);
        if (product.to_weight) {
            return `${formattedUnitPrice}/${product.uom_id.name}`;
        }
        return formattedUnitPrice;
    },
});