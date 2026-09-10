/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { useAsyncLockedMethod } from "@point_of_sale/app/hooks/hooks";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.validatePartialOrder = useAsyncLockedMethod(this.validatePartialOrder);
        // The "Crédito Cliente" tender (see pos_payment_method.py) is pure
        // internal bookkeeping created/consumed by the server itself
        // (`pos.order.apply_customer_credit` / `_redistribute_overpayment`)
        // -- it must never be offered as a manually-selectable payment
        // button, or a cashier could tender an arbitrary "credit" amount
        // with no real balance behind it. The checkbox below (see
        // ../../../views/pos_make_payment_views.xml's backend equivalent)
        // is the only supported way to apply it.
        this.payment_methods_from_config = this.payment_methods_from_config.filter(
            (paymentMethod) => !paymentMethod.is_credit_transfer
        );
    },

    /**
     * Current order's partner's banked POS credit balance, or 0 if there is
     * no partner. Drives both the visibility and the label of the "Use
     * Customer Credit" checkbox below.
     */
    get customerCreditBalance() {
        const partner = this.currentOrder.getPartner();
        return partner ? partner.pos_credit_balance || 0 : 0;
    },

    get useCustomerCredit() {
        return this.currentOrder.use_customer_credit ?? true;
    },

    /**
     * How much of the balance would actually apply right now: capped at
     * the order's own total, and 0 whenever the checkbox is off. Drives
     * `displayedTotalDue` below -- purely a checkout-screen display, never
     * touches `currentOrder.totalDue` itself (that stays the order's real
     * total, still needed as-is for invoicing/accounting/receipts).
     */
    get appliedCustomerCredit() {
        if (!this.useCustomerCredit) {
            return 0;
        }
        return Math.min(this.customerCreditBalance, this.currentOrder.totalDue);
    },

    /**
     * The "amount to pay" shown to the cashier, net of whatever credit is
     * about to be applied -- so the big number on screen always matches
     * what actually still needs to be tendered.
     */
    get displayedTotalDue() {
        return Math.max(this.currentOrder.totalDue - this.appliedCustomerCredit, 0);
    },

    /**
     * Only flips a flag stored on the order itself -- the actual
     * consumption (capped at the real available balance, never at
     * whatever's displayed here) happens server-side in
     * `pos.order.apply_customer_credit` when the order syncs, exactly like
     * the backend wizard's own checkbox.
     */
    toggleCustomerCredit(ev) {
        this.currentOrder.use_customer_credit = ev.target.checked;
    },

    /**
     * Deliberate, explicit "partial payment" validation: some payment has
     * been applied but not the full amount due. Unlike `validateOrder`,
     * this is only exposed through its own dedicated button in the UI (see
     * payment_screen.xml) so a cashier can never trigger it by accident.
     */
    async validatePartialOrder() {
        const validation = new OrderPaymentValidation({
            pos: this.pos,
            orderUuid: this.currentOrder.uuid,
        });
        // Set after construction: the base constructor destructures its
        // argument object (`{ pos, orderUuid, fastPaymentMethod }`) and
        // would drop an `allowPartial` key passed in there.
        validation.allowPartial = true;
        await validation.validateOrder(false);
    },
});
