/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);
        // Default to `true` for a brand-new order the same way core does
        // for its own booleans (see `to_invoice` right above this in core's
        // own `setup`) -- `??` (not `||`) so an explicit `false` coming
        // from the server on an existing order is respected.
        this.use_customer_credit = vals.use_customer_credit ?? true;
    },

    /**
     * True when the partner's banked POS credit (see
     * `pos.customer.credit`), together with whatever's already tendered,
     * fully covers this order -- i.e. it will end up `state == 'paid'` once
     * `pos.order.apply_customer_credit` runs server-side on sync, even
     * though nothing client-side has actually made `amountPaid` reach
     * `priceIncl` yet. Shared by `canBeValidated()` below (so the Validate
     * button isn't CSS-`disabled`/inert on a real touchscreen) and by
     * `order_payment_validation.js`'s `isOrderValid` (so the click, once it
     * lands, is actually accepted).
     */
    isCoveredByCustomerCredit() {
        const partner = this.getPartner();
        const anonymousId = this.config._consumidor_final_anonimo_id;
        const isRealPartner = partner && !(anonymousId && partner.id === anonymousId);
        const availableCredit =
            this.use_customer_credit && isRealPartner ? partner.pos_credit_balance || 0 : 0;
        if (availableCredit <= 0) {
            return false;
        }
        const remainingBeforeCredit = this.currency.round(this.priceIncl - this.amountPaid);
        return (
            remainingBeforeCredit > 0 &&
            this.currency.round(availableCredit - remainingBeforeCredit) >= 0
        );
    },

    canBeValidated() {
        return (
            super.canBeValidated() ||
            (this.isCoveredByCustomerCredit() && this._isValidEmptyOrder() && !this.isCustomerRequired)
        );
    },

    /**
     * `amount_return` (set by core, right below, to `this.change`) is what
     * the server's `_process_payment_lines` uses to decide whether to
     * create its own automatic cash "return"/change payment on sync (see
     * `point_of_sale/models/pos_order.py`) -- it does this unconditionally,
     * *before* `pos.order._redistribute_overpayment` (server-side, also on
     * sync) ever gets a look, so a non-zero `amount_return` always wins the
     * excess as plain cash change regardless of anything else. Zero it out
     * here when the cashier explicitly chose, via the "Sobrepago" prompt in
     * `order_payment_validation.js`'s `isOrderValid`, to leave the excess
     * for the server to redistribute/bank as customer credit instead.
     */
    setOrderPrices() {
        super.setOrderPrices();
        if (this.uiState.creditOverpaymentInstead) {
            this.amount_return = 0;
        }
    },
});
