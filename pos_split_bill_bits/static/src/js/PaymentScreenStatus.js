/** @odoo-module **/

import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status"; 
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenStatus.prototype, {
  get totalDueText() {
    return this.env.utils.formatCurrency(
      this.props.order.get_total_with_tax_split() +
        this.props.order.get_rounding_applied()
    );
  },
});