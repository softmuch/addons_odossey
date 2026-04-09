/** @odoo-module **/

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";

patch(ReceiptScreen.prototype, {
  orderDone() {
    if ( !this.currentOrder.is_split || this.currentOrder.split_done == this.currentOrder.to_split){
      this.currentOrder.uiState.screen_data.value = "";
      this.currentOrder.uiState.locked = true;
    }
    this._addNewOrder();
    this.pos.searchProductWord = "";
    const { name, props } = this.nextScreen;
    this.pos.showScreen(name, props);
  },
  get orderAmountPlusTip() {
    // replaced to changes split amount at payment success message
    const order = this.currentOrder;
    let orderTotalAmount = 0.0;
    if(order.is_split && order.to_split > 1){
      orderTotalAmount = order.get_total_with_tax_split();
    } else{
      orderTotalAmount = order.get_total_with_tax();
    } 
    const tip_product_id = this.pos.config.tip_product_id?.id;
    const tipLine = order.get_orderlines().find((line) => tip_product_id && line.product_id.id === tip_product_id);
    const tipAmount = tipLine ? tipLine.get_all_prices().priceWithTax : 0;
    const orderAmountStr = this.env.utils.formatCurrency(orderTotalAmount - tipAmount);
    if (!tipAmount) {
        return orderAmountStr;
    }
    const tipAmountStr = this.env.utils.formatCurrency(tipAmount);
    return `${orderAmountStr} + ${tipAmountStr} tip`;
}
});
