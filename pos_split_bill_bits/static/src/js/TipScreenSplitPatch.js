/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { TipScreen } from "@pos_restaurant/app/tip_screen/tip_screen";

const { onWillStart, onMounted, useState } = owl;

patch(TipScreen.prototype, {
  setup() {
    super.setup();
    this._totalAmount = this.currentOrder.is_Split
      ? this.currentOrder.get_total_with_tax_split()
      : this.currentOrder.get_total_with_tax();
  },
  goNextScreen() {
    if (
      !this.currentOrder.is_split ||
      this.currentOrder.split_done == this.currentOrder.to_split
    ) {
      this.pos.removeOrder(this.currentOrder);
      if (!this.pos.config.module_pos_restaurant) {
        this.pos.add_new_order();
      }
    }
    const { name, props } = this.nextScreen;
    this.pos.showScreen(name, props);
  },

  goBack() {
    if (!this.currentOrder.finalized)
      while (this.currentOrder.paymentlines.length > 0) {
        this.currentOrder.remove_paymentline(this.currentOrder.paymentlines[0]);
      }
    this.pos.showScreen("FloorScreen");
  },
});
