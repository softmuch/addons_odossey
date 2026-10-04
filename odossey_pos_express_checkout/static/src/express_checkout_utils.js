// selectedTable must be cleared BEFORE creating the order: pos_restaurant's
// createNewOrder() attaches table_id = selectedTable to any order created while
// a table is still selected, which silently turned "new express order" into
// "another order on the same table".
//
// onlyLocal: reuse only orders never sent to the server (used where the pending
// orders cannot be refreshed first, see refreshExpressOrders).
export function getOrCreateExpressOrder(pos, { onlyLocal = false } = {}) {
    pos.selectedTable = null;

    const order =
        pos.models["pos.order"].find(
            (o) =>
                o.is_express_checkout &&
                !o.is_delivery &&
                !o.finalized &&
                !o.table_id &&
                !(onlyLocal && typeof o.id === "number")
        ) || pos.add_new_order();

    order.is_express_checkout = true;
    return order;
}

// A pending express order may have been paid or cancelled on another terminal
// without this one noticing (device synchronisation misses two writes made within
// the same second). Re-read them so a finished order is never resumed here.
export async function refreshExpressOrders(pos) {
    const ids = pos.models["pos.order"]
        .filter((o) => o.is_express_checkout && !o.finalized && typeof o.id === "number")
        .map((o) => o.id);
    if (!ids.length) {
        return;
    }
    try {
        await pos.data.read("pos.order", ids);
    } catch (e) {
        console.warn("Express checkout: could not refresh pending orders", e);
    }
}
