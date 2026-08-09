import { patch } from "@web/core/utils/patch";
import { ProductCard } from "@point_of_sale/app/components/product_card/product_card";

patch(ProductCard.props, {
    price: { type: String, optional: true },
});
