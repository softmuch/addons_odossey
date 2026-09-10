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
     * The partner's banked POS credit (see `pos.customer.credit`) that
     * would actually apply to this order right now: 0 whenever the
     * checkbox is off, there's no real partner (never the anonymous one --
     * it has no account to credit against), or nothing is banked. Shared by
     * `isCoveredByCustomerCredit()` and `getDefaultAmountDueToPayIn()`
     * below so both agree on the exact same figure the server's own
     * `apply_customer_credit()` will use at sync time.
     */
    _availableCustomerCredit() {
        const partner = this.getPartner();
        const anonymousId = this.config._consumidor_final_anonimo_id;
        const isRealPartner = partner && !(anonymousId && partner.id === anonymousId);
        return this.use_customer_credit && isRealPartner ? partner.pos_credit_balance || 0 : 0;
    },

    /**
     * How much of the available customer credit would actually apply right
     * now, capped at both the balance and what's left after real tenders
     * (`apply_customer_credit` server-side never applies more than its own
     * residual -- see its own docstring -- so this mirrors that cap
     * exactly). 0 whenever the checkbox is off, there's nothing banked, or
     * real tenders already cover the order on their own. Shared by
     * `isCoveredByCustomerCredit()` below and by
     * `order_payment_validation.js`'s own partial-payment remaining-balance
     * message, so both always agree on the same figure the server will
     * actually apply.
     */
    appliedCustomerCredit() {
        const availableCredit = this._availableCustomerCredit();
        if (availableCredit <= 0) {
            return 0;
        }
        const remainingBeforeCredit = this.currency.round(this.priceIncl - this.amountPaid);
        if (remainingBeforeCredit <= 0) {
            return 0;
        }
        return Math.min(availableCredit, remainingBeforeCredit);
    },

    /**
     * True when the partner's banked POS credit, together with whatever's
     * already tendered, fully covers this order -- i.e. it will end up
     * `state == 'paid'` once `pos.order.apply_customer_credit` runs
     * server-side on sync, even though nothing client-side has actually
     * made `amountPaid` reach `priceIncl` yet. Shared by `canBeValidated()`
     * below (so the Validate button isn't CSS-`disabled`/inert on a real
     * touchscreen) and by `order_payment_validation.js`'s `isOrderValid`
     * (so the click, once it lands, is actually accepted).
     */
    isCoveredByCustomerCredit() {
        const remainingBeforeCredit = this.currency.round(this.priceIncl - this.amountPaid);
        return remainingBeforeCredit > 0 && this.appliedCustomerCredit() >= remainingBeforeCredit;
    },

    /**
     * Net of whatever customer credit will actually apply at sync time --
     * otherwise a cashier tapping a payment method (Efectivo, Tarjeta...)
     * after ticking "Use Credit" gets the FULL order total pre-filled
     * (core's own `remainingDue`, credit-unaware) instead of just the real
     * cash/card portion, defeating the checkbox: they'd end up tendering
     * the whole order in cash, `amount_paid` would already equal
     * `amount_total` by the time the order syncs, and the server's own
     * `apply_customer_credit()` (residual <= 0 -> no-op) would then never
     * create the credit payment line at all -- silently ignoring the
     * credit exactly as reported.
     *
     * Only nets against the REMAINING due at the moment this new line is
     * about to be added (`this.remainingDue`, i.e. before this line's own
     * amount is counted) -- matching `apply_customer_credit`'s own
     * `residual = amount_total - amount_paid` at sync time, since only
     * real payment lines exist client-side (the credit line itself is only
     * ever created server-side). The cashier can still freely overtype a
     * bigger or smaller amount afterwards -- overpayment redistribution/
     * banking and partial-payment handling are untouched, both already
     * cope with a real residual left after credit is applied.
     */
    getDefaultAmountDueToPayIn(paymentMethod) {
        const amount = super.getDefaultAmountDueToPayIn(paymentMethod);
        const remaining = this.remainingDue;
        const availableCredit = this._availableCustomerCredit();
        if (remaining <= 0 || availableCredit <= 0) {
            return amount;
        }
        const net = this.currency.round(remaining - availableCredit);
        return net > 0 ? net : 0;
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
