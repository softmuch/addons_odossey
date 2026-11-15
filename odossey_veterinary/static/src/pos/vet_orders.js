import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";

const POS_RETURN_KEY = "odossey_veterinary.pos_return";
const AGENDA_URL = "/odoo/action-odossey_veterinary.vet_appointment_action";

const LOTS_QUESTION = "Do you want to load the SN/Lots linked to the Sales Order?";

/**
 * Cash desk of the clinic: the orders of the visits not paid yet, always up to date. The server notifies the open
 * tills (VET_ORDERS_CHANGED) when the veterinarian closes a consultation or another till charges an order.
 */
patch(PosStore.prototype, {
    async afterProcessServerData() {
        const res = await super.afterProcessServerData(...arguments);
        this.vetOrders = { count: 0, revision: 0 };
        this.data.connectWebSocket("VET_ORDERS_CHANGED", () => this.vetRefreshOrders());
        this.vetRefreshOrders();
        return res;
    },

    /** Back to the agenda when the till was opened from the Veterinary app or the user only sees that app. */
    async redirectToBackend() {
        let fromVeterinary = false;
        try {
            fromVeterinary = browser.sessionStorage.getItem(POS_RETURN_KEY) === "1";
        } catch {
            // no session storage: rely on the scope of the user
        }
        if (!fromVeterinary) {
            try {
                fromVeterinary = await user.hasGroup("odossey_veterinary.group_vet_scope_vet_only");
            } catch {
                fromVeterinary = false;
            }
        }
        if (fromVeterinary) {
            window.location = AGENDA_URL;
            return;
        }
        return super.redirectToBackend(...arguments);
    },

    async vetRefreshOrders() {
        try {
            this.vetOrders.count = await this.data.call("sale.order", "vet_pos_count_orders", [this.config.id]);
            this.vetOrders.revision++;
        } catch {
            // offline: the list is read again when the till reconnects or the button is pressed
        }
    },

    /** Charge the order of a visit in one click: no "settle / down payment" question, lots of the vet kept. */
    async vetSettleOrder(saleOrderId) {
        const saleOrder = await this._getSaleOrder(saleOrderId);
        const current = this.getOrder();
        if (current && !current.isEmpty()) {
            this.addNewOrder();
        }
        if (saleOrder.partner_id) {
            this.getOrder().setPartner(saleOrder.partner_id);
        }
        const fiscalPosition = saleOrder.fiscal_position_id;
        this.getOrder().update({ fiscal_position_id: fiscalPosition });
        // the veterinarian already chose the lot of each medication: load it without asking
        const dialog = this.dialog;
        const originalAdd = dialog.add;
        const lotsQuestion = _t(LOTS_QUESTION);
        dialog.add = (Comp, props, options) => {
            if (props && (props.body === lotsQuestion || props.body === LOTS_QUESTION) && props.confirm) {
                props.confirm();
                return () => {};
            }
            return originalAdd.call(dialog, Comp, props, options);
        };
        try {
            await this.settleSO(saleOrder, fiscalPosition);
        } finally {
            dialog.add = originalAdd;
        }
        const lines = this.getOrder().lines;
        if (lines.length) {
            this.selectOrderLine(this.getOrder(), lines.at(-1));
        }
    },
});

export class VetOrdersDialog extends Component {
    static template = "odossey_veterinary.VetOrdersDialog";
    static components = { Dialog };
    static props = { close: Function, onSelect: Function };

    setup() {
        this.pos = usePos();
        this.ui = useState(useService("ui"));
        this.state = useState({ search: "", orders: [], loading: true });
        this.searchLater = debounce(() => this.load(), 250);
        this.revision = this.pos.vetOrders?.revision;
        onWillStart(() => this.load());
        // live refresh while the list is open
        onMounted(() => {
            this.interval = setInterval(() => {
                if (this.pos.vetOrders && this.pos.vetOrders.revision !== this.revision) {
                    this.revision = this.pos.vetOrders.revision;
                    this.load();
                }
            }, 500);
        });
        onWillUnmount(() => clearInterval(this.interval));
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.orders = await this.pos.data.call("sale.order", "vet_pos_search_orders", [
                this.pos.config.id,
                this.state.search,
            ]);
        } finally {
            this.state.loading = false;
        }
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        this.searchLater();
    }

    formatDate(value) {
        return value ? formatDateTime(deserializeDateTime(value)) : "";
    }

    formatAmount(value) {
        return this.env.utils.formatCurrency(value);
    }

    badgeClass(state) {
        return (
            {
                unpaid: "text-bg-danger",
                partial: "text-bg-danger",
                in_pos: "text-bg-warning",
            }[state] || "text-bg-success"
        );
    }

    async select(order) {
        this.props.close();
        await this.props.onSelect(order.id);
    }
}

patch(ControlButtons.prototype, {
    get vetOrdersCount() {
        return this.pos.vetOrders?.count || 0;
    },
    onClickVetOrders() {
        this.dialog.add(VetOrdersDialog, {
            onSelect: (saleOrderId) => this.pos.vetSettleOrder(saleOrderId),
        });
    },
});
