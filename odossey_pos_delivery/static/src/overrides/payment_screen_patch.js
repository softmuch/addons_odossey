import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.deliveryOrm = useService("orm");
    },

    async toggleIsDelivery() {
        const order = this.currentOrder;
        order.is_delivery = !order.is_delivery;
        if (order.is_delivery && !order.get_partner()) {
            await this.pos.selectPartner();
        }
    },

    async _finalizeValidation() {
        const isDelivery = this.currentOrder.is_delivery;
        const partner = this.currentOrder.get_partner();
        const amountTotal = this.currentOrder.get_total_with_tax
            ? this.currentOrder.get_total_with_tax()
            : this.currentOrder.amount_total || 0;

        if (isDelivery && !partner) {
            await this.pos.selectPartner();
            if (!this.currentOrder.get_partner()) {
                return;
            }
        }

        await super._finalizeValidation(...arguments);

        if (isDelivery) {
            try {
                const sessionId = this.pos.session?.id || false;
                const p = partner || this.currentOrder.get_partner();
                await this.deliveryOrm.create("pos.delivery.order", [
                    {
                        partner_id: p?.id || false,
                        partner_name: p?.name || "",
                        partner_phone: p?.phone || p?.mobile || "",
                        delivery_address: [p?.street, p?.street2]
                            .filter(Boolean)
                            .join(" "),
                        delivery_state: "preparing",
                        payment_state: "paid",
                        amount_total: amountTotal,
                        pos_session_id: sessionId,
                    },
                ]);
            } catch (e) {
                console.error("Error al crear pedido delivery:", e);
            }
        }
    },
});
