import { Base } from "@point_of_sale/app/models/related_models";
import { registry } from "@web/core/registry";
import { serializeDateTime } from "@web/core/l10n/dates";
import { SERIALIZABLE_MODELS } from "@point_of_sale/app/models/related_models";
import { DataServiceOptions } from "@point_of_sale/app/models/data_service_options";
import { uuidv4 } from "@point_of_sale/utils";
import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order"

patch(DataServiceOptions.prototype, {
  get databaseTable() {
    return {
      ...super.databaseTable,
      "ab_pos.order.change": {
        key: "uuid",
        condition: (record) =>
          record.order_id?.finalized && typeof record.order_id.id === "number",
      },
      "ab_pos.order.change.line": {
        key: "uuid",
        condition: (record) => false,
      },
    };
  },
  get dynamicModels() {
    return [
      ...super.dynamicModels ?? [],
      "ab_pos.order.change",
      "ab_pos.order.change.line",
    ];
  },
});

patch(PosOrder.prototype, {
  setup(vals) {
    super.setup(vals);

    if (this._isSelfOrder()) {
      const trackingNumber = this._selfOrderTrackingNumber(this.pos_reference)
      if (!trackingNumber.includes(this.tracking_number.toString())) {
        this.tracking_number = trackingNumber
      }
    }
  },

  _isSelfOrder() {
    return this.pos_reference?.includes('Kiosk') || this.pos_reference?.includes('Self-Order')
  },

  // CREDIT: https://github.com/odoo/odoo/blob/67a5213238ca95ea6cdab2c40943cc593b2308e5/addons/pos_self_order/static/src/app/models/order.js
  _selfOrderTrackingNumber(posReference) {
    const arrRef = posReference.split(" ")[1].split("-");
    const sessionID = arrRef[0][4];
    const sequence = arrRef[2].substr(2, 2);
    return "S" + sessionID + sequence;
  },

})

export class OrderChange extends Base {
  static pythonModel = "ab_pos.order.change";

  setup(vals) {
    super.setup(vals);
    // console.debug("OrderChange.setup()", vals, this)

    this.created_at =
      vals.created_at || serializeDateTime(luxon.DateTime.now());
    this.uuid = vals.uuid ? vals.uuid : uuidv4();

    if (!vals.lines) {
      this.lines = [];
    }
  }
}

registry
  .category("pos_available_models")
  .add(OrderChange.pythonModel, OrderChange);

export class OrderChangeLine extends Base {
  static pythonModel = "ab_pos.order.change.line";

  setup(vals) {
    super.setup(vals);
    // console.debug("OrderChangeLine.setup()", vals, this)

    this.uuid = vals.uuid ? vals.uuid : uuidv4();
    this.state = vals.state || "cooking";
  }
}

registry
  .category("pos_available_models")
  .add(OrderChangeLine.pythonModel, OrderChangeLine);

if (SERIALIZABLE_MODELS) {
  SERIALIZABLE_MODELS.push("ab_pos.order.change", "ab_pos.order.change.line");
}
