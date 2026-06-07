import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const DELIVERY_FIELDS = [
    "id", "partner_name", "partner_phone", "delivery_address",
    "note", "delivery_state", "payment_state", "amount_total",
    "start_time", "estimated_time", "shipping_cost", "pos_order_uid",
];

const NEXT_STATE = {
    preparing: "ready",
    ready: "sent",
    sent: "delivered",
};

const NEXT_STATE_LABEL = {
    preparing: "Ready",
    ready: "Sent",
    sent: "Delivered",
};

export class DeliveryScreen extends Component {
    static template = "odossey_pos_delivery.DeliveryScreen";
    static name = "DeliveryScreen";
    static storeOnOrder = false;

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            orders: [],
            loading: false,
            error: "",
        });
        onMounted(() => this.loadOrders());
    }

    async loadOrders() {
        this.state.loading = true;
        this.state.error = "";
        try {
            await this.orm.call("pos.delivery.order", "sync_kds_states", [], {
                session_id: this.pos.session?.id || false,
            });
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            const todayStr = today.toISOString().slice(0, 19).replace("T", " ");
            this.state.orders = await this.orm.searchRead(
                "pos.delivery.order",
                [["start_time", ">=", todayStr]],
                DELIVERY_FIELDS,
                { order: "start_time desc" }
            );
        } catch (e) {
            this.state.error = _t("Error loading delivery orders.");
            console.error(e);
        } finally {
            this.state.loading = false;
        }
    }

    get preparingOrders() {
        return this.state.orders.filter((o) => o.delivery_state === "preparing");
    }
    get readyOrders() {
        return this.state.orders.filter((o) => o.delivery_state === "ready");
    }
    get sentOrders() {
        return this.state.orders.filter((o) => o.delivery_state === "sent");
    }
    get deliveredOrders() {
        return this.state.orders.filter((o) => o.delivery_state === "delivered");
    }

    formatTime(datetimeStr) {
        if (!datetimeStr) return "-";
        const d = new Date(datetimeStr.replace(" ", "T"));
        return d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
    }

    formatAmount(amount) {
        return parseFloat(amount || 0).toFixed(2);
    }

    getNextStateLabel(state) {
        return NEXT_STATE_LABEL[state] || "";
    }

    canAdvance(order) {
        return !!NEXT_STATE[order.delivery_state];
    }

    async advanceState(order) {
        const newState = NEXT_STATE[order.delivery_state];
        if (!newState) return;
        try {
            await this.orm.write("pos.delivery.order", [order.id], { delivery_state: newState });
            order.delivery_state = newState;
            this.state.orders = [...this.state.orders];
        } catch (e) {
            console.error("Error updating delivery state:", e);
        }
    }

    openNewDeliveryOrder() {
        const order = this.pos.add_new_order();
        order.is_delivery = true;
        this.pos.showScreen("ProductScreen");
    }

    openDeliveryOrderEdit(record) {
        if (record.delivery_state !== "preparing") return;
        if (!record.pos_order_uid) {
            this.notification.add(
                _t("Order not linked. Cannot edit."),
                { type: "warning" }
            );
            return;
        }
        const order = this.pos.models["pos.order"].find(
            (o) => o.uuid === record.pos_order_uid
        );
        if (!order) {
            this.notification.add(
                _t("Order not found in memory. POS may have been restarted."),
                { type: "warning" }
            );
            return;
        }
        order.delivery_record_id = record.id;
        this.pos.selectedOrderUuid = order.uuid;
        this.pos.showScreen("ProductScreen");
    }

    back() {
        const prev = this.pos.previousScreen;
        this.pos.showScreen(prev && prev !== "DeliveryScreen" ? prev : "ProductScreen");
    }
}

registry.category("pos_screens").add("DeliveryScreen", DeliveryScreen);
