// selectedTable must be cleared BEFORE creating the order: pos_restaurant's
// createNewOrder() attaches table_id = selectedTable to any order created while
// a table is still selected, which silently turned "new express order" into
// "another order on the same table".
export function getOrCreateExpressOrder(pos) {
    pos.selectedTable = null;

    const order =
        pos.models["pos.order"].find((o) => o.is_express_checkout && !o.finalized && !o.table_id) ||
        pos.add_new_order();

    order.is_express_checkout = true;
    return order;
}
