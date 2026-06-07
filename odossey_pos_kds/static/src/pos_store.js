import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { changesToOrder } from "@point_of_sale/app/models/utils/order_change";
import { SERIALIZABLE_MODELS } from "@point_of_sale/app/models/related_models";

patch(PosStore.prototype, {
  /**
   * @override
   */
  async sendOrderInPreparationUpdateLastChange(order, cancelled = false, initialState = "cooking") {
    if (order?.is_delivery) {
      return this.sendDeliveryOrderToKds(order, initialState);
    }

    const {
      new: toAdd,
      cancelled: toRemove,
      noteUpdated,
    } = changesToOrder(order, false, new Set(), cancelled);

    const orderChange = this.models["ab_pos.order.change"].create({
      order_id: order,
      sequence_number: order.ab_pos_changes.length + 1,
    });

    let addLine = (line, cancelled = false) => {
      const product = this.models["product.product"].get(line.product_id);
      /**
       * @typedef { import("./models").OrderChangeLine } OrderChangeLine
       * @type OrderChangeLine
       */
      const model = this.models["ab_pos.order.change.line"];
      const changeLine = model.create({
        change_id: orderChange,
        product_id: product,
        qty: cancelled ? -line.quantity : line.quantity,
        note: line.note,
        line_uuid: line.uuid,
        state: initialState,
        // Adding the attributes directly does not work
        // attribute_value_ids: line.attribute_value_ids?.map((attr) => attr.id),
      });
      changeLine.attribute_value_ids = line.attribute_value_ids;
    };

    toAdd.forEach((line) => addLine(line));
    toRemove.forEach((line) => addLine(line, true));

    // handle note updates
    noteUpdated.forEach((line) => addLine({ ...line, quantity: 0 }));

    await super.sendOrderInPreparationUpdateLastChange(order, cancelled);

    // since commit 0c8f0d7 (), sendOrderInPreparationUpdateLastChange does no longer sync orders
    if (!SERIALIZABLE_MODELS) {
      await this.syncAllOrders({
        orders: [order],
      });
    }
  },

  /**
   * Send order to KDS screen only — NO kitchen printer.
   * Use instead of sendOrderInPreparationUpdateLastChange when printing must be suppressed.
   */
  async sendToKdsOnly(order, initialState = "cooking") {
    const {
      new: toAdd,
      cancelled: toRemove,
      noteUpdated,
    } = changesToOrder(order, false, new Set(), false);

    const orderChange = this.models["ab_pos.order.change"].create({
      order_id: order,
      sequence_number: order.ab_pos_changes.length + 1,
    });

    let addLine = (line, cancelled = false) => {
      const product = this.models["product.product"].get(line.product_id);
      const model = this.models["ab_pos.order.change.line"];
      const changeLine = model.create({
        change_id: orderChange,
        product_id: product,
        qty: cancelled ? -line.quantity : line.quantity,
        note: line.note,
        line_uuid: line.uuid,
        state: initialState,
      });
      changeLine.attribute_value_ids = line.attribute_value_ids;
    };

    toAdd.forEach((line) => addLine(line));
    toRemove.forEach((line) => addLine(line, true));
    noteUpdated.forEach((line) => addLine({ ...line, quantity: 0 }));

    order.updateLastOrderChange();

    if (!SERIALIZABLE_MODELS) {
      await this.syncAllOrders({ orders: [order] });
    }
  },

  /**
   * For delivery orders: all changes (additions AND removals) go to the SINGLE existing commanda.
   * On first send: creates the commanda with original lines (is_delta=false).
   * On updates: adds delta lines (is_delta=true, signed qty) to the same commanda.
   * The Vue KDS computes netDelta = sum(is_delta lines) to show a single (+n) or (-n) indicator.
   */
  async sendDeliveryOrderToKds(order, initialState = "cooking") {
    const {
      new: toAdd,
      cancelled: toRemove,
      noteUpdated,
    } = changesToOrder(order, false, new Set(), false);

    if (!toAdd.length && !toRemove.length && !noteUpdated.length) {
      return;
    }

    const existingChanges = order.ab_pos_changes || [];
    const isUpdate = existingChanges.length > 0;
    let orderChange;

    if (isUpdate) {
      orderChange = existingChanges[existingChanges.length - 1];
      orderChange.is_modified = true;
      orderChange.setDirty();
    } else {
      orderChange = this.models["ab_pos.order.change"].create({
        order_id: order,
        sequence_number: 1,
        is_modified: false,
      });
    }

    const addLine = (line, cancelled = false, isDelta = false) => {
      const product = this.models["product.product"].get(line.product_id);
      const model = this.models["ab_pos.order.change.line"];
      const changeLine = model.create({
        change_id: orderChange,
        product_id: product,
        qty: cancelled ? -line.quantity : line.quantity,
        note: line.note,
        line_uuid: line.uuid,
        state: initialState,
        is_delta: isDelta,
      });
      changeLine.attribute_value_ids = line.attribute_value_ids;
    };

    toAdd.forEach((line) => addLine(line, false, isUpdate));
    toRemove.forEach((line) => addLine(line, true, isUpdate));
    noteUpdated.forEach((line) => addLine({ ...line, quantity: 0 }, false, false));

    order.updateLastOrderChange();

    if (!SERIALIZABLE_MODELS) {
      await this.syncAllOrders({ orders: [order] });
    }
  },

  /**
   * Without this override the categories might get restricted by preparation printers
   * @override https://github.com/odoo/odoo/blob/1ca879612fe546108fd1067839924ae8c25b2bb9/addons/point_of_sale/static/src/app/store/pos_store.js#L1057
   */
  get orderPreparationCategories() {
    return new Set();
  }
});
