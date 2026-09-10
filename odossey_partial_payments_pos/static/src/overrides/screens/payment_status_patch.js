/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";

patch(PaymentScreenStatus.prototype, {
    /**
     * Core computes `isComplete`/`isRemaining` from `order.remainingDue`
     * alone, which only ever counts REAL payment lines (the credit line is
     * only ever created server-side on sync, see `pos.order.
     * apply_customer_credit`) -- so as soon as credit is about to cover the
     * rest, core still sees a positive "Remaining $X" gap and renders the
     * red "Restantes" line, even though the order is, in effect, fully
     * settled. `order.isCoveredByCustomerCredit()` is the same check
     * `canBeValidated()`/`isOrderValid` already rely on for that: true only
     * when there's a real gap (`remainingBeforeCredit > 0`) fully closed by
     * available credit, never when cash/card alone already covers the
     * order (that's a real overpay, left to the existing "Sobrepago"
     * flow/redistribution untouched).
     */
    get isComplete() {
        return this.order.isCoveredByCustomerCredit() || super.isComplete;
    },

    /**
     * Forces the "Cambio"/change branch instead of "Restantes" once
     * credit closes the gap -- `order.change` (core, unpatched) already
     * resolves to 0 here on its own: its own formula only produces a
     * non-zero value for a NEGATIVE `totalDue - amountPaid` (real cash
     * overpay), and the credit-covered gap is by definition positive, not
     * negative. So switching to this branch is enough to show "Cambio
     * $0,00" (green) without needing to also override `amountText`.
     */
    get isRemaining() {
        if (this.order.isCoveredByCustomerCredit()) {
            return false;
        }
        return super.isRemaining;
    },
});
