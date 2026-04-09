/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch"; 
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(ProductScreen.prototype, {
  async _setValue(val) {
    if (this.currentOrder && this.currentOrder.split_done > 0) {
      // await this.dialog.add(AlertDialog, {
      //   title: "Error",
      //   body: "Cannot change product quantity after payment is made",
      // });
      return;
    }
    super._setValue(val);
  },
});
