import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
// eslint-disable-next-line no-undef
const _odoo = typeof odoo !== "undefined" ? odoo : {};

const DELIVERY_FIELDS = [
    "id", "partner_name", "partner_phone", "delivery_address",
    "note", "delivery_state", "payment_state", "amount_total",
    "start_time", "estimated_time", "shipping_cost", "pos_order_uid", "hidden",
];

const NEXT_STATE = {
    preparing: "ready",
    ready: "sent",
    sent: "delivered",
};

const PREV_STATE = {
    ready: "preparing",
    sent: "ready",
    delivered: "sent",
};

export class DeliveryScreen extends Component {
    static template = "odossey_pos_delivery.DeliveryScreen";
    static name = "DeliveryScreen";
    static storeOnOrder = false;
    static props = {};

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.state = useState({
            orders: [],
            loading: false,
            error: "",
        });
        this._onDeliveryStateChange = this._onDeliveryStateChange.bind(this);
        onMounted(() => {
            const accessToken = _odoo.access_token;
            if (accessToken) {
                this._busType = `${accessToken}-DELIVERY_STATE_CHANGE`;
                this.busService.subscribe(this._busType, this._onDeliveryStateChange);
            }
            this.loadOrders();
        });
        onWillUnmount(() => {
            if (this._busType) {
                this.busService.unsubscribe(this._busType, this._onDeliveryStateChange);
            }
        });
    }

    _onDeliveryStateChange(payload) {
        const order = this.state.orders.find((o) => o.id === payload.delivery_id);
        if (order) {
            order.delivery_state = payload.delivery_state;
            this.state.orders = [...this.state.orders];
        } else {
            // Order not in local list (new order or created from another terminal).
            this.loadOrders();
        }
    }

    label(key) {
        const map = {
            preparing: _t("Preparing"),
            ready: _t("Ready"),
            sent: _t("Sent"),
            delivered: _t("Delivered"),
            paid: _t("Paid"),
            unpaid: _t("Unpaid"),
            noOrders: _t("No orders."),
            back: _t("Back"),
            newOrder: _t("New Order"),
            time: _t("Time"),
            customer: _t("Customer"),
            address: _t("Address"),
            phone: _t("Phone"),
            payment: _t("Payment"),
            total: _t("Total"),
            advanceAll: _t("Advance All"),
            hideAllPaid: _t("Hide All"),
            deleteOrderTitle: _t("Delete delivery order?"),
            deleteOrderBody: _t("This will permanently delete this delivery order. This action cannot be undone."),
        };
        return map[key] || key;
    }

    async loadOrders() {
        this.state.error = "";
        if (!this.state.loading) {
            this.state.loading = true;
            try {
                await this.orm.call("pos.delivery.order", "sync_kds_states", [], {
                    session_id: this.pos.session?.id || false,
                });
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                const todayStr = today.toISOString().slice(0, 19).replace("T", " ");
                this.state.orders = await this.orm.searchRead(
                    "pos.delivery.order",
                    [["start_time", ">=", todayStr], ["hidden", "=", false]],
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
        return this.state.orders.filter(
            (o) => o.delivery_state === "delivered" && !o.hidden
        );
    }

    get deliveredPaidVisible() {
        return this.deliveredOrders.filter((o) => o.payment_state === "paid");
    }

    async hideDeliveredOrder(order) {
        try {
            await this.orm.write("pos.delivery.order", [order.id], { hidden: true });
            order.hidden = true;
            this.state.orders = [...this.state.orders];
        } catch (e) {
            console.error("Error hiding delivery order:", e);
        }
    }

    async hideAllDelivered() {
        const ids = this.deliveredPaidVisible.map((o) => o.id);
        if (!ids.length) return;
        try {
            await this.orm.write("pos.delivery.order", ids, { hidden: true });
            for (const order of this.state.orders) {
                if (ids.includes(order.id)) order.hidden = true;
            }
            this.state.orders = [...this.state.orders];
        } catch (e) {
            console.error("Error hiding delivery orders:", e);
        }
    }

    formatTime(datetimeStr) {
        if (!datetimeStr) return "-";
        const d = new Date(datetimeStr.replace(" ", "T"));
        return d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
    }

    formatAmount(amount) {
        return parseFloat(amount || 0).toFixed(2);
    }

    openable(order) {
        return order.payment_state !== "paid";
    }

    onRowClick(order) {
        if (order.payment_state === "paid") {
            this.notification.add(_t("Paid orders cannot be reopened."), { type: "info" });
            return;
        }
        if (!order.pos_order_uid) {
            this.notification.add(_t("Order has no POS reference."), { type: "warning" });
            return;
        }
        const posOrder = this.pos.models["pos.order"].find(
            (o) => o.uuid === order.pos_order_uid
        );
        if (!posOrder) {
            this.notification.add(
                _t("Order not found in memory. POS may have been restarted."),
                { type: "warning" }
            );
            return;
        }
        posOrder.delivery_record_id = order.id;
        this.pos.selectedOrderUuid = posOrder.uuid;
        this.pos.showScreen("ProductScreen");
    }

    getNextStateLabel(state) {
        const labels = {
            preparing: _t("Ready"),
            ready: _t("Sent"),
            sent: _t("Delivered"),
        };
        return labels[state] || "";
    }

    getPrevStateLabel(state) {
        const labels = {
            ready: _t("Preparing"),
            sent: _t("Ready"),
            delivered: _t("Sent"),
        };
        return labels[state] || "";
    }

    canAdvance(order) {
        return !!NEXT_STATE[order.delivery_state];
    }

    canRetreat(order) {
        return !!PREV_STATE[order.delivery_state];
    }

    async advanceState(order) {
        const newState = NEXT_STATE[order.delivery_state];
        if (!newState) return;
        try {
            await this.orm.write("pos.delivery.order", [order.id], { delivery_state: newState });
            order.delivery_state = newState;
            this.state.orders = [...this.state.orders];
            await this.orm.call("pos.delivery.order", "sync_delivery_to_kds", [], {
                delivery_id: order.id,
                new_delivery_state: newState,
            });
        } catch (e) {
            console.error("Error advancing delivery state:", e);
        }
    }

    async retreatState(order) {
        const prevState = PREV_STATE[order.delivery_state];
        if (!prevState) return;
        try {
            await this.orm.write("pos.delivery.order", [order.id], { delivery_state: prevState });
            order.delivery_state = prevState;
            this.state.orders = [...this.state.orders];
            await this.orm.call("pos.delivery.order", "sync_delivery_to_kds", [], {
                delivery_id: order.id,
                new_delivery_state: prevState,
            });
        } catch (e) {
            console.error("Error retreating delivery state:", e);
        }
    }

    async advanceAll(stateKey) {
        const orders = [...this.state.orders.filter((o) => o.delivery_state === stateKey)];
        for (const order of orders) {
            await this.advanceState(order);
        }
    }

    deleteOrder(order) {
        this.dialog.add(ConfirmationDialog, {
            title: this.label("deleteOrderTitle"),
            body: this.label("deleteOrderBody"),
            confirm: async () => {
                try {
                    await this.orm.unlink("pos.delivery.order", [order.id]);
                    this.state.orders = this.state.orders.filter((o) => o.id !== order.id);
                } catch (e) {
                    console.error("Error deleting delivery order:", e);
                }
            },
        });
    }

    openNewDeliveryOrder() {
        const order = this.pos.add_new_order();
        order.is_delivery = true;
        this.pos.showScreen("ProductScreen");
    }

    back() {
        const prev = this.pos.previousScreen;
        this.pos.showScreen(prev && prev !== "DeliveryScreen" ? prev : "ProductScreen");
    }
}

registry.category("pos_screens").add("DeliveryScreen", DeliveryScreen);
