import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";

patch(ProductScreen.prototype, {
    getProductPrice(product) {
        const formattedUnitPrice = product.displayPriceUnit;
        if (product.to_weight) {
            return `${formattedUnitPrice}/${product.uom_id.name}`;
        }
        return formattedUnitPrice;
    },
});