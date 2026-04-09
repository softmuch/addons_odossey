/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ConnectionLostError, RPCError } from "@web/core/network/rpc";
import { handleRPCError } from "@point_of_sale/app/errors/error_handlers";
import { serializeDateTime } from "@web/core/l10n/dates";
import { useState } from "@odoo/owl";


patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        // Restore n_payments from the order (persisted to server on each change),
        // so a page reload in the middle of a split keeps the correct value.
        const currentOrder = this.pos.get_order();
        this.splitState = useState({ value: currentOrder?.n_payments || 1 });
    },
    get n_payments() {
        return this.splitState.value;
    },
    _updatePaymentAmount() {
        const currentOrder = this.pos.get_order();
        if (currentOrder.payment_ids.length > 0) {
            currentOrder.payment_ids[0].set_amount(currentOrder.get_total_with_tax_split());
        }
    },
    increment_n_payments() {
        var currentOrder = this.pos.get_order();
        var missing_splits = currentOrder.to_split - currentOrder.split_done;
        if (this.splitState.value >= missing_splits) {
            this.splitState.value = missing_splits;
        } else {
            this.splitState.value++;
            currentOrder.n_payments++;
        }
        this._updatePaymentAmount();
        // Mark as pending — will be saved on next _finalizeValidation sync
        this.pos.addPendingOrder([currentOrder.id]);
    },
    decrement_n_payments() {
        var currentOrder = this.pos.get_order();
        if (this.splitState.value > 1) {
            this.splitState.value--;
            currentOrder.n_payments--;
            this._updatePaymentAmount();
            // Mark as pending — will be saved on next _finalizeValidation sync
            this.pos.addPendingOrder([currentOrder.id]);
        }
    },
    async _finalizeValidation() {
        if (this.currentOrder.is_paid_with_cash() || this.currentOrder.get_change()) {
            this.hardwareProxy.openCashbox();
        }
        this.currentOrder.date_order = serializeDateTime(luxon.DateTime.now());
        for (const line of this.paymentLines) {
            if (!line.amount === 0) {
                this.currentOrder.remove_paymentline(line);
            }
        }
        this.pos.addPendingOrder([this.currentOrder.id]);
        if (this.currentOrder.is_split) {
            await this.currentOrder.splitDone();
        } else {
            this.currentOrder.state = "paid";
        }
        this.env.services.ui.block();
        let syncOrderResult;
        // Keep the order as draft until all splits are done; finalize on last payment
        let option;
        if (!this.currentOrder.is_split || this.currentOrder.split_done == this.currentOrder.to_split) {
            option = {};
        } else {
            option = { throw: true };
        }
        try {
            syncOrderResult = await this.pos.syncAllOrders(option);
            if (!syncOrderResult) {
                return;
            }
            // Invoice download if needed
            if (this.shouldDownloadInvoice() && this.currentOrder.is_to_invoice()) {
                if (this.currentOrder.raw.account_move) {
                    await this.invoiceService.downloadPdf(this.currentOrder.raw.account_move);
                } else {
                    throw {
                        code: 401,
                        message: "Backend Invoice",
                        data: { order: this.currentOrder },
                    };
                }
            }
        } catch (error) {
            if (error instanceof ConnectionLostError) {
                this.pos.showScreen(this.nextScreen);
                Promise.reject(error);
            } else if (error instanceof RPCError) {
                this.currentOrder.state = "draft";
                handleRPCError(error, this.dialog);
            } else {
                throw error;
            }
            return error;
        } finally {
            this.env.services.ui.unblock();
        }

        const postPushOrders = syncOrderResult.filter((order) => order.wait_for_push_order());
        if (postPushOrders.length > 0) {
            await this.postPushOrderResolve(postPushOrders.map((order) => order.id));
        }

        await this.afterOrderValidation(!!syncOrderResult && syncOrderResult.length > 0);
    },
    async afterOrderValidation() {
        let nextScreen = this.nextScreen;
        let switchScreen = false;
        if (
            nextScreen === "ReceiptScreen" &&
            this.currentOrder.nb_print === 0 &&
            this.pos.config.iface_print_auto
        ) {
            const invoiced_finalized = this.currentOrder.is_to_invoice() ? this.currentOrder.finalized : true;

            if (invoiced_finalized) {
                this.pos.printReceipt(this.currentOrder);

                if (this.pos.config.iface_print_skip_screen) {
                    this.currentOrder.set_screen_data({ name: "" });
                    this.currentOrder.uiState.locked = true;
                    switchScreen = this.currentOrder.uuid === this.pos.selectedOrderUuid;
                    nextScreen = "ProductScreen";
                    if (switchScreen) {
                        this.selectNextOrder();
                    }
                }
            }
        } else {
            switchScreen = true;
        }

        if (switchScreen) {
            this.pos.showScreen(nextScreen);
        }
    },
    get paymentLines() {
        return this.currentOrder.payment_ids;
    }
});
