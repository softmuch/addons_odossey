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

/**
 * Create or update a pos.delivery.order for the given POS order.
 * Returns the delivery record ID.
 * Update-only fields: partner info, amount_total.
 * delivery_state/payment_state/start_time are NOT overwritten on update.
 */
async function upsertDeliveryRecord(orm, order, posSession) {
    const partner = order.get_partner();
    const amountTotal = order.get_total_with_tax
        ? order.get_total_with_tax()
        : order.amount_total || 0;
    const updateVals = {
        partner_id: partner?.id || false,
        partner_name: partner?.name || "",
        partner_phone: partner?.phone || partner?.mobile || "",
        delivery_address: partner ? buildDeliveryAddress(partner) : "",
        amount_total: amountTotal,
    };

    // 1. In-memory reference from this session
    if (order.delivery_record_id) {
        await orm.write("pos.delivery.order", [order.delivery_record_id], updateVals);
        return order.delivery_record_id;
    }

    // 2. Search by UUID (handles page-reload case)
    if (order.uuid) {
        const existing = await orm.searchRead(
            "pos.delivery.order",
            [["pos_order_uid", "=", order.uuid]],
            ["id"],
            { limit: 1 }
        );
        if (existing.length) {
            const id = existing[0].id;
            await orm.write("pos.delivery.order", [id], updateVals);
            return id;
        }
    }

    // 3. Create new record
    const [id] = await orm.create("pos.delivery.order", [{
        ...updateVals,
        delivery_state: "preparing",
        payment_state: "unpaid",
        pos_session_id: posSession?.id || false,
        pos_order_uid: order.uuid,
    }]);
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
                const id = await upsertDeliveryRecord(
                    this.env.services.orm, order, this.pos.session
                );
                order.delivery_record_id = id;
            } catch (e) {
                console.error("Error upserting delivery record:", e);
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
                const id = await upsertDeliveryRecord(
                    this.env.services.orm, order, this.pos.session
                );
                order.delivery_record_id = id;
            } catch (e) {
                console.error("Error upserting delivery record (print):", e);
            }
            this.pos.showScreen("DeliveryScreen");
        }
    },
});
