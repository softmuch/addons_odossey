import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

function isValidDeliveryPartner(partner, posConfig) {
    if (!partner) return false;
    if (!partner.street || !partner.city) return false;
    const anonId = posConfig?.partner_id?.id || posConfig?.partner_id;
    if (anonId && partner.id === anonId) return false;
    return true;
}

function buildDeliveryAddress(partner) {
    return [partner.street, partner.city, partner.zip].filter(Boolean).join(", ");
}

async function createDeliveryRecord(orm, order, posSession, paymentState = "unpaid") {
    const partner = order.get_partner();
    const amountTotal = order.get_total_with_tax
        ? order.get_total_with_tax()
        : order.amount_total || 0;
    const [id] = await orm.create("pos.delivery.order", [
        {
            partner_id: partner?.id || false,
            partner_name: partner?.name || "",
            partner_phone: partner?.phone || partner?.mobile || "",
            delivery_address: partner ? buildDeliveryAddress(partner) : "",
            delivery_state: "preparing",
            payment_state: paymentState,
            amount_total: amountTotal,
            pos_session_id: posSession?.id || false,
            pos_order_uid: order.uuid,
        },
    ]);
    return id;
}

patch(ActionpadWidget.prototype, {
    async submitOrder() {
        const order = this.currentOrder;
        if (order?.is_delivery) {
            if (!isValidDeliveryPartner(order.get_partner(), this.pos.config)) {
                this.env.services.notification.add(
                    _t("Delivery: please select a customer with complete address (street and city)."),
                    { type: "warning" }
                );
                return;
            }
        }

        await super.submitOrder(...arguments);

        if (order?.is_delivery) {
            try {
                const id = await createDeliveryRecord(
                    this.env.services.orm, order, this.pos.session, "unpaid"
                );
                order.delivery_record_id = id;
            } catch (e) {
                console.error("Error creating delivery record:", e);
            }
            this.pos.showScreen("DeliveryScreen");
        }
    },

    async orderAndPrint() {
        const order = this.currentOrder;
        if (order?.is_delivery) {
            if (!isValidDeliveryPartner(order.get_partner(), this.pos.config)) {
                this.env.services.notification.add(
                    _t("Delivery: please select a customer with complete address (street and city)."),
                    { type: "warning" }
                );
                return;
            }
        }

        await super.orderAndPrint(...arguments);

        if (order?.is_delivery) {
            try {
                const id = await createDeliveryRecord(
                    this.env.services.orm, order, this.pos.session, "unpaid"
                );
                order.delivery_record_id = id;
            } catch (e) {
                console.error("Error creating delivery record (print):", e);
            }
            this.pos.showScreen("DeliveryScreen");
        }
    },
});
