from odoo import models, fields, api
from uuid import uuid4
from urllib.parse import urlencode
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval

class KitchenScreen(models.Model):
    _name = "ab_pos.kitchen_screen"
    _inherit = ["pos.load.mixin"]
    _description = "Preparation Display for the kitchen"

    name = fields.Char("Name", required=True)
    config_ids = fields.Many2many(
        "pos.config",
        "ab_pos_kitchen_screen_pos_config_rel",
        "kitchen_id",
        "config_id",
        string="Point of Sale",
    )

    access_token = fields.Char("Access Token", default=lambda self: uuid4().hex[:16])
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    wait_time = fields.Integer(
        "Current wait time",
        default=0,
        help="Wait time in minutes. Set to 0 to disable. Will be displayed at the top of the self-order menu if aks_self_order is installed.",
    )

    filter = fields.Char(
        "Custom Filter",
        default="[]",
        help="Filter orders according to specified criteria",
    )

    default_notification = fields.Selection([
        ('none', 'None'),
        ('alert', 'Alert'),
        ('champagne', 'Champagne'),
        ('dingaling', 'Dingaling'),
        ('dripecho', 'Dripecho'),
        ('rooster', 'Rooster'),
    ], string="Default Notification", default="none")

    orderline_group_ids = fields.One2many("ab_pos.orderline_group", "kitchen_id", string="Orderline groups")

    def open_kitchen(self, params: dict = {}):
        self.ensure_one()
        path = "/odossey_pos_kds/app/"
        params.update({"ks": self.id})
        # Set default categories
        params.update({"categ": self.orderline_group_ids.category_ids.ids})
        # Set default notification
        params.update({"n": self.default_notification})

        return {
            "type": "ir.actions.act_url",
            "url": path + "?" + urlencode(params, doseq=True),
            "target": "self",
        }

    def _ensure_access_token(self):
        # Code taken from addons/portal/models/portal_mixin.py
        if not self.access_token:
            self.sudo().write({"access_token": uuid4().hex[:16]})
        return self.access_token

    def _get_bus_channel_name(self):
        return self._ensure_access_token()

    def _load_data_fields(self):
        return {
            "product.product": [
                "id",
                "display_name",
                "pos_categ_ids",
                "type",
                "product_tmpl_id",
                "valid_product_template_attribute_line_ids",
                *(
                    ["ab_stock_out_of_stock", "ab_stock_disabled_attributes"]
                    if "ab_stock_out_of_stock" in self.env["product.template"]._fields
                    else []
                ),
            ],
            "pos.config": ["id", "name", "epson_printer_ip"],
            "pos.category": ["id", "name", "parent_id", "child_ids"],
            "restaurant.floor": ["id", "name"],
            "restaurant.table": ["id", "table_number", "floor_id", "active"],
            "hr.employee": ["id", "name", "user_id"],
            "res.users": [
                "id",
                "name",
                "display_name",
                "lang",
                *(["employee_id"] if self._has_model("hr.employee") else []),
            ],
            "pos.printer": [
                "name",
                "proxy_ip",
                "product_categories_ids",
                "printer_type",
                "epson_printer_ip",
            ],
            "pos.order": self.env["pos.order"]._load_pos_data_fields(None),
            "pos.order.line": [
                "id",
                "uuid",
                "combo_line_ids",
                "combo_parent_id",
                "refunded_qty",
                "refunded_orderline_id",
            ],
            "res.partner": [
                "id",
                "name",
                "street",
                "city",
                "state_id",
                "country_id",
                "vat",
                "lang",
                "phone",
                "zip",
                "mobile",
                "email",
                "comment",
            ],
        }

    def _load_product_product(self, categories, fields):
        domain = [
            *self.env["product.product"]._check_company_domain(self.company_id),
            ("available_in_pos", "=", True),
            ("sale_ok", "=", True),
            ("pos_categ_ids", "in", categories.ids),
        ]

        # load all services
        domain = expression.OR([domain, [("type", "=", "service")]])

        products = self.env["product.product"].search(domain)
        #add combo items
        product_combo = products.filtered(lambda p: p['type'] == 'combo')
        product_in_combo = product_combo.combo_ids.combo_item_ids.product_id
        products |= product_in_combo

        return products.read(fields, load=None)

    def _has_module(self, module: str) -> bool:
        return (
            self.env["ir.module.module"].search_count(
                [("state", "=", "installed"), ("name", "=", module)]
            )
            > 0
        )

    def _has_model(self, model: str) -> bool:
        return self.env.get(model, None) is not None

    def load_orders(self, domain=[]):
        self.ensure_one()
        fields = self._load_data_fields()

        orders = self.env["pos.order"].search(expression.AND([domain, self.custom_order_filter()]))
        changes = self.env["ab_pos.order.change"].search(
            [("order_id", "in", orders.ids)]
        )
        lines = self.env["ab_pos.order.change.line"].search(
            [("change_id", "in", changes.ids)]
        )

        return {
            "pos.order": orders.read(fields["pos.order"], load=None),
            "pos.order.line": orders.lines.read(fields["pos.order.line"], load=None),
            "ab_pos.order.change": changes.read(load=None),
            "ab_pos.order.change.line": lines.read(load=None),
            "res.partner": self.env["res.partner"].search_read(
                [("id", "in", orders.partner_id.ids)], fields["res.partner"]
            ),
        }

    def custom_order_filter(self):
        try:
            return safe_eval(self.filter)
        except Exception:
            return []

    def load_data(self):
        self.ensure_one()
        fields = self._load_data_fields()

        configs = (
            self.config_ids if self.config_ids else self.env["pos.config"].search([])
        )
        open_sessions = configs.filtered(
            lambda c: c.has_active_session
        ).current_session_id

        categories = configs.iface_available_categ_ids
        if not categories:
            categories = self.env["pos.category"].search([])
        else:
            categories |= self.env["pos.category"].search([('id', 'child_of', categories.ids)])

        floors = self.env["restaurant.floor"].search(
            [("pos_config_ids", "in", configs.ids)],
        )

        data = {
            "pos.config": configs.read(fields["pos.config"], load=None),
            "product.product": self._load_product_product(
                categories, fields["product.product"]
            ),
            "pos.category": categories.read(fields["pos.category"], load=None),
            "restaurant.floor": floors.read(fields["restaurant.floor"], load=None),
            "restaurant.table": self.env["restaurant.table"].search_read(
                [("floor_id", "in", floors.ids)], fields["restaurant.table"], load=None
            ),
            "pos.printer": self.env["pos.printer"].search_read(
                [("id", "in", configs.printer_ids.ids)],
                fields["pos.printer"],
                load=None,
            ),
            "product.template.attribute.line": self.env["product.template.attribute.line"].search_read(
                [], load=None
            ),
            "product.template.attribute.value": self.env[
                "product.template.attribute.value"
            ].search_read([], load=None),
            "res.users": self.env["res.users"].search_read(
                [], fields["res.users"], load=None
            ),
            **self.load_orders([("session_id", "in", open_sessions.ids)]),
        }

        if self._has_model("hr.employee"):
            data["hr.employee"] = self.env["hr.employee"].search_read(
                [], fields["hr.employee"]
            )

        return data
    
    def set_delivery_time(self, delivery_time):
        delivery_locs = self.config_ids.ab_self_order_delivery_locs
        delivery_locs.write({
            "delivery_time": delivery_time,
            "delivery_time_var": 0,
        })

    @api.model
    def _load_pos_data_domain(self, data):
        config_id = data["pos.config"]["data"][0]["id"]
        return [("config_ids", "=", config_id)]
