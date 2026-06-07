import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.deliveryOrm = useService("orm");
    },

    async _finalizeValidation() {
        const order = this.currentOrder;
        const isDelivery = order?.is_delivery;

        if (isDelivery) {
            const partner = order.get_partner();
            const anonId =
                this.pos.config.partner_id?.id || this.pos.config.partner_id;
            const valid =
                partner &&
                partner.street &&
                partner.city &&
                !(anonId && partner.id === anonId);
            if (!valid) {
                this.notification.add(
                    _t("Delivery: please select a customer with complete address (street and city)."),
                    { type: "warning" }
                );
                return;
            }
        }

        // Capture delivery snapshot before super — order reference may change after payment
        const snap = isDelivery
            ? {
                  recordId: order.delivery_record_id,
                  partner: order.get_partner(),
                  amountTotal: order.get_total_with_tax
                      ? order.get_total_with_tax()
                      : order.amount_total || 0,
                  orderUuid: order.uuid,
                  sessionId: this.pos.session?.id || false,
              }
            : null;

        await super._finalizeValidation(...arguments);

        if (snap) {
            try {
                if (snap.recordId) {
                    await this.deliveryOrm.write("pos.delivery.order", [snap.recordId], {
                        payment_state: "paid",
                        amount_total: snap.amountTotal,
                    });
                } else {
                    const p = snap.partner;
                    await this.deliveryOrm.create("pos.delivery.order", [
                        {
                            partner_id: p?.id || false,
                            partner_name: p?.name || "",
                            partner_phone: p?.phone || p?.mobile || "",
                            delivery_address: p
                                ? [p.street, p.city, p.zip].filter(Boolean).join(", ")
                                : "",
                            delivery_state: "preparing",
                            payment_state: "paid",
                            amount_total: snap.amountTotal,
                            pos_session_id: snap.sessionId,
                            pos_order_uid: snap.orderUuid,
                        },
                    ]);
                }
            } catch (e) {
                console.error("Error saving delivery record (payment):", e);
            }
            this.pos.showScreen("DeliveryScreen");
        }
    },
});
