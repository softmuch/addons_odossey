from odoo import api, fields, models
from odoo.exceptions import AccessError
from uuid import uuid4
import logging
from odoo import tools

_logger = logging.getLogger(__name__)

ORDER_IDS_KEY = "abichinger_kitchen_screen.order_ids"

class PosOrder(models.Model):
    _inherit = "pos.order"

    ab_pos_changes = fields.One2many(
        "ab_pos.order.change", "order_id", string="Order Change", copy=True
    )
    
    # Override: https://github.com/abichinger/odoo/blob/f9de1eef6dd403157c0222dc75de85c8b7b59e3c/addons/point_of_sale/models/pos_order.py
    @api.model
    def _load_pos_data_domain(self, data):
        if self.env.context.get("abichinger_kitchen_screen", False):
            return [('state', 'in', ['draft', 'paid', 'cancel']), ('session_id', '=', data['pos.session']['data'][0]['id'])]
        return super()._load_pos_data_domain(data)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res.note_order_change()
        return res

    def write(self, vals):
        res = super().write(vals)
        self.note_order_change()
        return res


    def note_order_change(self):
        callbacks: tools.Callbacks = self._cr.precommit
        if ORDER_IDS_KEY not in callbacks.data:
            callbacks.add(lambda: self._precommit())

        order_ids: set = callbacks.data.get(ORDER_IDS_KEY, set([]))
        for order in self:
            order_ids.add(order.id)
        callbacks.data[ORDER_IDS_KEY] = order_ids
                

    def _precommit(self):
        callbacks: tools.Callbacks = self._cr.precommit
        order_ids = list(callbacks.data.get(ORDER_IDS_KEY, set([])))
        if len(order_ids) == 0:
            return
        self.env['pos.order'].sudo().browse(order_ids).send_order_update_notification()


    def send_order_update_notification(self):
        messages: dict[str, dict] = {}
        for order in self:
            kitchen_ids = order.config_id._get_all_kitchen_ids()
            for kitchen_id in kitchen_ids:
                channel = kitchen_id._get_bus_channel_name()
                if messages.get(channel, None):
                    order_ids: list[int] = messages.get(channel)['order_ids']
                    order_ids.append(order.id)
                else:
                    messages[channel] = {
                        'order_ids': [order.id],
                        'kitchen_id': kitchen_id.id
                    }
                
        for channel, message in messages.items():
            self.env["bus.bus"]._sendone(channel, "SYNC_ORDERS", message)

    # Override: https://github.com/odoo/odoo/blob/f283dddefc621779063283c27a1374c1d5b3fa36/addons/point_of_sale/models/pos_order.py
    @api.model
    def sync_from_ui(self, orders):
        res = super().sync_from_ui(orders)

        config_ids = [o["config_id"] for o in res['pos.order'] if o["config_id"]]
        config_id = next(iter(config_ids), None)
        if config_id is None:
            return res
        
        data = {
            "pos.config": {"data": [{"id": config_id}]},
            "pos.order": {
                "data": res['pos.order'],
            },
        }

        for model in ["ab_pos.order.change", "ab_pos.order.change.line"]:
            try:
                data[model] = self.env[model]._load_pos_data(data)
            except AccessError as e:
                data[model] = {"data": [], "error": e.args[0]}
            
            res[model] = data[model]['data']

        return res
    
    def update_priority(self, value):
        self.ab_pos_changes.update_priority(value)

class OrderChange(models.Model):
    _name = "ab_pos.order.change"
    _inherit = ["pos.load.mixin"]
    _description = "POS Order Change"

    created_at = fields.Datetime(required=True)

    order_id = fields.Many2one(
        "pos.order", string="Order Ref", ondelete="cascade", required=True, index=True
    )
    lines = fields.One2many(
        "ab_pos.order.change.line", "change_id", string="Change Lines", copy=True
    )
    sequence_number = fields.Integer(
        string="Sequence Number",
        help="A order-unique sequence number for the change",
        default=1,
    )
    uuid = fields.Char(string='Uuid', readonly=True, default=lambda self: str(uuid4()), copy=False)

    priority = fields.Integer(string="Priority", default=0)

    def update_priority(self, value):
        if not self:
            return
        
        self.write({
            "priority": value
        })
        self.order_id.note_order_change()

    @api.model
    def _load_pos_data_domain(self, data):
        order_ids = [order["id"] for order in data["pos.order"]["data"]]
        return [("order_id", "in", order_ids)]


class OrderChangeLine(models.Model):
    _name = "ab_pos.order.change.line"
    _inherit = ["pos.load.mixin"]
    _description = "POS Order Change Line"

    change_id = fields.Many2one(
        "ab_pos.order.change",
        string="Order Change Ref",
        ondelete="cascade",
        required=True,
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain=[("sale_ok", "=", True)],
        required=True,
        change_default=True,
    )
    qty = fields.Float("Quantity", digits="Product Unit of Measure", default=1)

    state = fields.Selection(
        [
            ("cooking", "Cooking"),
            ("ready", "Ready"),
            ("done", "Done"),
            ("cancel", "Canceled"),
        ],
        "Status",
        required=True,
        copy=False,
        default="cooking",
        index=True,
    )

    note = fields.Char("Internal Note added by the waiter.")
    attribute_value_ids = fields.Many2many(
        "product.template.attribute.value", string="Selected Attributes"
    )
    uuid = fields.Char(string='Uuid', readonly=True, default=lambda self: str(uuid4()), copy=False)
    line_uuid = fields.Char(default='')

    @api.model
    def _load_pos_data_domain(self, data):
        change_ids = [change["id"] for change in data["ab_pos.order.change"]["data"]]
        return [("change_id", "in", change_ids)]

    def set_state(self, state: str):
        self.write({"state": state})

        order: PosOrder = self.change_id.order_id
        order.note_order_change()
