import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";

// Paid orders can sit on tables whose floor is archived / not loaded in the POS
// (or tables with no floor). Stock pos_restaurant dereferences table.floor_id
// unguarded, which crashes the whole TicketScreen render (blank screen).
patch(TicketScreen.prototype, {
    getTable(order) {
        const table = order.getTable();
        if (!table) {
            return;
        }
        const floor = table.floor_id;
        const prefix =
            floor && this.pos.models["restaurant.floor"].length > 0 ? `${floor.name}/` : "";
        return prefix + table.getName();
    },
});

patch(PosOrder.prototype, {
    getName() {
        if (this.config.module_pos_restaurant) {
            const table = this.getTable();
            if (table && !table.floor_id) {
                return table.table_number.toString();
            }
        }
        return super.getName(...arguments);
    },
});

// Opening Órdenes -> Pagado with no current order (e.g. straight from the floor
// plan or after a reload) and clicking a paid order renders the Refund
// ActionpadWidget, whose pos_restaurant categoryCount calls getOrderChanges()
// with get_order() === undefined and crashes the screen. Return "no changes".
patch(PosStore.prototype, {
    getOrderChanges(skipped = false, order = this.get_order()) {
        if (!order) {
            return {
                nbrOfSkipped: 0,
                nbrOfChanges: 0,
                noteUpdated: {},
                orderlines: {},
                count: 0,
            };
        }
        return super.getOrderChanges(skipped, order);
    },
});
