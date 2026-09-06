import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { PayFreelyPopup } from "@odossey_pos_edit_backend/app/components/pay_freely_popup/pay_freely_popup";

patch(ControlButtons.prototype, {
    /**
     * Frontend counterpart of the backend's "Pagar libremente" button (see
     * `point_of_sale.view_pos_order_tree_inherit_pay_freely` /
     * `pay.freely.wizard` in odossey_pos_edit_backend's Python models): applies an
     * amount to the current order's customer's own oldest open POS orders,
     * from a register that's actually in front of the customer instead of
     * needing the backend. Reuses the exact same wizard model/logic via RPC
     * (`get_partner_debt_info`/`pay_from_pos`) rather than reimplementing
     * the split-across-orders logic in JS.
     */
    async clickPayFreely() {
        const partner = this.currentOrder.getPartner();
        if (!partner) {
            this.dialog.add(AlertDialog, {
                title: _t("Cliente requerido"),
                body: _t("Elegí un cliente para poder pagar libremente sus órdenes pendientes."),
            });
            return;
        }

        const info = await this.pos.data.call("pay.freely.wizard", "get_partner_debt_info", [
            partner.id,
        ]);
        if (!info.total_residual) {
            this.notification.add(
                _t("%s no tiene órdenes POS pendientes de pago.", partner.name),
                { type: "warning" }
            );
            return;
        }

        const banks = this.pos.models["res.bank"] ? this.pos.models["res.bank"].getAll() : [];
        const paymentMethods = this.pos.models["pos.payment.method"].getAll();
        const payload = await makeAwaitable(this.dialog, PayFreelyPopup, {
            partner,
            totalResidual: info.total_residual,
            totalResidualLabel: this.pos.env.utils.formatCurrency(info.total_residual),
            paymentMethods,
            banks,
        });
        if (!payload) {
            return;
        }

        const result = await this.pos.data.call("pay.freely.wizard", "pay_from_pos", [
            {
                partner_id: partner.id,
                amount: payload.amount,
                payment_method_id: payload.payment_method_id,
                payment_date: new Date().toISOString().split("T")[0],
                l10n_latam_check_number: payload.number,
                l10n_latam_check_bank_id: payload.bank_id,
                l10n_latam_check_issuer_vat: payload.issuer_vat,
                l10n_latam_check_type: payload.check_type,
                l10n_latam_check_issue_date: payload.issue_date,
                l10n_latam_check_payment_date: payload.payment_date,
            },
        ]);

        this.notification.add(
            _t(
                "Pago de %(amount)s aplicado a %(count)s orden(es). Saldo restante: %(remaining)s.",
                {
                    amount: this.pos.env.utils.formatCurrency(result.applied),
                    count: result.orders_count,
                    remaining: this.pos.env.utils.formatCurrency(result.remaining),
                }
            ),
            { type: "success" }
        );
    },
});
