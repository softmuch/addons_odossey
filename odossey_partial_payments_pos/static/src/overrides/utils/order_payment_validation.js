/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";

/**
 * Adds an explicit, opt-in "partial payment" path to the order validation
 * flow. This is deliberately NOT wired into the normal Validate button: a
 * cashier must not be able to under-charge a customer with a stray click.
 * It is only reachable through the dedicated "Partial Payment" button (see
 * ../screens/payment_screen.js / .xml), which sets `allowPartial = true` on
 * the instance right after constructing it.
 *
 * Note: `allowPartial` is set as a plain instance property rather than
 * threaded through the constructor, because the base `constructor({ pos,
 * orderUuid, fastPaymentMethod })` destructures its argument object and
 * would silently drop any extra key (like `allowPartial`) before it ever
 * reaches `setup()`.
 *
 * `isOrderValid` has no extension point around its `!this.order.isPaid()`
 * gate, so this patch fully redefines the method (copied from
 * @point_of_sale/app/utils/order_payment_validation.js) with a single new
 * branch added around that gate. Every other check is left untouched. If
 * core ever changes `isOrderValid`, this override needs to be re-synced by
 * hand.
 */
patch(OrderPaymentValidation.prototype, {
    async isOrderValid(isForceValidate) {
        if (this.order.isRefundInProcess()) {
            return false;
        }

        if (this.order.getOrderlines().length === 0 && this.order.isToInvoice()) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Empty Order"),
                body: _t(
                    "There must be at least one product in your order before it can be validated and invoiced."
                ),
            });
            return false;
        }

        if (
            (this.order.isToInvoice() || this.order.getShippingDate()) &&
            !this.order.getPartner()
        ) {
            const confirmed = await ask(this.pos.dialog, {
                title: _t("Please select the Customer"),
                body: _t(
                    "You need to select the customer before you can invoice or ship an order."
                ),
            });
            if (confirmed) {
                this.pos.selectPartner();
            }
            return false;
        }

        const partner = this.order.getPartner();
        if (
            this.order.getShippingDate() &&
            !(partner.name && partner.street && partner.city && partner.country_id)
        ) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Incorrect address for shipping"),
                body: _t("The selected customer needs an address."),
            });
            return false;
        }

        if (!this.order.presetRequirementsFilled) {
            const { field, message } = this.order.uiState.requiredPartnerDetails || {};
            this.pos.dialog.add(AlertDialog, {
                title: field ? _t("%s required", field) : _t("Missing required"),
                body: message || _t("Some required information is missing."),
            });
            return false;
        }

        if (
            !this.pos.currency.isZero(this.order.priceIncl) &&
            this.order.payment_ids.length === 0
        ) {
            this.pos.notification.add(_t("Select a payment method to validate the order."));
            return false;
        }

        if (!this.order.isPaid() || this.invoicing) {
            if (this.invoicing || !this.allowPartial) {
                return false;
            }

            // A partial payment must be traceable to a real customer -- same
            // rule/helper as l10n_latam_check_ext's check-payment guard
            // (`pos.config._consumidor_final_anonimo_id`, loaded into the
            // frontend by l10n_ar_pos for AR companies only; falls back to
            // just requiring *some* partner if that id isn't available).
            const partner = this.order.getPartner();
            const anonymousId = this.pos.config._consumidor_final_anonimo_id;
            if (!partner || (anonymousId && partner.id === anonymousId)) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Cliente requerido"),
                    body: _t(
                        'Elegí un cliente distinto de "Consumidor Final Anónimo" antes de hacer un pago parcial.'
                    ),
                });
                return false;
            }

            // A deliberate partial payment is only allowed if the cashier
            // actually applied some payment: don't let an empty, zero-paid
            // order be validated as "partial".
            const hasEffectivePayment = this.order.payment_ids.some(
                (line) => line.isDone() && line.getAmount() > 0
            );
            if (!hasEffectivePayment) {
                return false;
            }

            const remaining = this.order.priceIncl - this.order.amountPaid;
            const confirmed = await new Promise((resolve) => {
                this.pos.dialog.add(ConfirmationDialog, {
                    title: _t("Partial Payment"),
                    body: _t(
                        "This order will be left Partially Paid. The remaining balance of %s will still be due and can be collected later.",
                        this.pos.env.utils.formatCurrency(remaining)
                    ),
                    confirm: () => resolve(true),
                    cancel: () => resolve(false),
                });
            });
            if (!confirmed) {
                return false;
            }

            if (!this.order._isValidEmptyOrder()) {
                return false;
            }

            return true;
        }

        // The exact amount must be paid if there is no cash payment method defined.
        if (
            Math.abs(this.order.priceIncl - this.order.amountPaid + this.order.appliedRounding) >
            0.00001
        ) {
            if (!this.pos.models["pos.payment.method"].some((pm) => pm.is_cash_count)) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Cannot return change without a cash payment method"),
                    body: _t(
                        "There is no cash payment method available in this point of sale to handle the change.\n\n Please pay the exact amount or add a cash payment method in the point of sale configuration"
                    ),
                });
                return false;
            }
        }

        // if the change is too large, it's probably an input error, make the user confirm.
        if (
            !isForceValidate &&
            this.order.priceIncl > 0 &&
            this.order.priceIncl * 1000 < this.order.amountPaid
        ) {
            this.pos.dialog.add(ConfirmationDialog, {
                title: _t("Please Confirm Large Amount"),
                body:
                    _t("Are you sure that the customer wants to  pay") +
                    " " +
                    this.pos.env.utils.formatCurrency(this.order.amountPaid) +
                    " " +
                    _t("for an order of") +
                    " " +
                    this.pos.env.utils.formatCurrency(this.order.priceIncl) +
                    " " +
                    _t('? Clicking "Confirm" will validate the payment.'),
                confirm: () => this.validateOrder(true),
            });
            return false;
        }

        if (!this.order._isValidEmptyOrder()) {
            return false;
        }

        return true;
    },
});
