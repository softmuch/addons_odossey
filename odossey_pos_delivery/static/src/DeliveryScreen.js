import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { registry } from "@web/core/registry";
import { NewDeliveryOrderPopup } from "./NewDeliveryOrderPopup";

const DELIVERY_FIELDS = [
    "id", "partner_name", "partner_phone", "delivery_address",
    "note", "delivery_state", "payment_state", "amount_total",
    "start_time", "estimated_time", "shipping_cost",
];

const STATE_LABELS = {
    preparing: "En preparación",
    ready: "Listo",
    sent: "Enviado",
    delivered: "Entregado",
};

const NEXT_STATE = {
    preparing: "ready",
    ready: "sent",
    sent: "delivered",
};

const NEXT_STATE_LABEL = {
    preparing: "Listo",
    ready: "Enviado",
    sent: "Entregado",
};

export class DeliveryScreen extends Component {
    static template = "odossey_pos_delivery.DeliveryScreen";
    static name = "DeliveryScreen";
    static storeOnOrder = false;

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.state = useState({
            orders: [],
            loading: false,
            error: "",
        });
        onMounted(() => this.loadOrders());
    }

    async loadOrders() {
        this.state.loading = true;
        try {
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
            this.state.error = "Error al cargar pedidos de delivery.";
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
            console.error("Error al actualizar estado:", e);
        }
    }

    openNewOrderForm() {
        this.dialog.add(NewDeliveryOrderPopup, {
            confirm: async (data) => {
                try {
                    const sessionId = this.pos.session?.id || false;
                    const [id] = await this.orm.create("pos.delivery.order", [
                        {
                            ...data,
                            delivery_state: "preparing",
                            payment_state: "unpaid",
                            pos_session_id: sessionId,
                        },
                    ]);
                    const [newOrder] = await this.orm.searchRead(
                        "pos.delivery.order",
                        [["id", "=", id]],
                        DELIVERY_FIELDS
                    );
                    this.state.orders = [newOrder, ...this.state.orders];
                } catch (e) {
                    console.error("Error al crear pedido delivery:", e);
                }
            },
        });
    }

    back() {
        const prev = this.pos.previousScreen;
        this.pos.showScreen(prev && prev !== "DeliveryScreen" ? prev : "ProductScreen");
    }
}

registry.category("pos_screens").add("DeliveryScreen", DeliveryScreen);
