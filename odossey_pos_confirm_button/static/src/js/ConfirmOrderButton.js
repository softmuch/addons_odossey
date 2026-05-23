/** @odoo-module **/

import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(ControlButtons.prototype, {
    /**
     * Force-confirm a POS order stuck open after a fiscal printer error.
     *
     * Why a custom Python endpoint instead of syncAllOrders():
     *   When the printer fails, super()._finalizeValidation() is never called,
     *   so payment lines are never synced to the server. The order exists in the
     *   DB as 'draft' with product lines but zero payment records.
     *   syncAllOrders() alone cannot finalize it because action_pos_order_paid()
     *   requires amount_paid >= amount_total. The endpoint creates the missing
     *   payment records and calls action_pos_order_paid() in a single server call.
     */
    async clickConfirmOrder() {
        const order = this.pos.get_order();
        if (!order) return;

        // --- Confirmation popup ---
        let userConfirmed = false;
        await new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t('Conferma Ordine'),
                body: _t('Sei sicuro di voler confermare l\'ordine? Si consiglia fare questo solo in caso di errore durante il pagamento.'),
                confirm: () => { userConfirmed = true; resolve(); },
                cancel: () => resolve(),
            });
        });
        if (!userConfirmed) return;

        this.dialog.closeAll();

        // --- Build payment payload (skip change lines) ---
        const payments = order.payment_ids
            .filter((p) => !p.is_change && p.amount > 0)
            .map((p) => ({
                payment_method_id: p.payment_method_id.id,
                amount: p.amount,
                uuid: p.uuid || '',
            }));

        this.env.services.ui.block();
        let result;
        try {
            // Ensure the order exists on the server before calling force_confirm_order.
            // If the order was never synced (created in JS but server never received it),
            // the endpoint would return "Order not found". Mark it pending and sync first.
            this.pos.addPendingOrder([order.id]);
            await this.pos.syncAllOrders({});

            result = await this.pos.data.call(
                'pos.order',
                'force_confirm_order',
                [order.uuid, payments]
            );
        } catch (error) {
            this.env.services.notification.add(
                _t('Errore durante la conferma: ') + (error.message || String(error)),
                { type: 'danger', title: _t('Errore') }
            );
            return;
        } finally {
            this.env.services.ui.unblock();
        }

        if (!result || !result.success) {
            this.env.services.notification.add(
                result?.error || _t('Errore sconosciuto'),
                { type: 'danger', title: _t('Errore nella conferma dell\'ordine') }
            );
            return;
        }

        // Remove from local JS model → table freed on FloorScreen
        this.pos.data.localDeleteCascade(order);

        this.pos.showScreen('FloorScreen');
    },
});
