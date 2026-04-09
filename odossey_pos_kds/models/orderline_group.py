from odoo import fields, models

class OrderLineGroup(models.Model):
    _name = "ab_pos.orderline_group"
    _description = "Groups of products within an order"

    kitchen_id = fields.Many2one(
        "ab_pos.kitchen_screen", string="Kitchen Display", ondelete="cascade", required=True
    )

    sequence = fields.Integer(
        string="Sequence", help="Determines the order of the stages", index=True
    )
    name = fields.Char(string="Name", required=True)

    category_ids = fields.Many2many(
        "pos.category",
        string="POS Categories",
        help="POS Categories (incl. subcategories)",
    )

    attribute_ids = fields.Many2many(
        "product.attribute.value",
        string="Product Attributes",
    )

    def _load_data(self):
        data = []
        
        for group in self.sorted("sequence"):
            categories = self.env["pos.category"].search(
                [
                    "|",
                    ("id", "in", group.category_ids.ids),
                    ("id", "child_of", group.category_ids.ids),
                ]
            )

            attributes = self.env["product.template.attribute.value"].search(
                [('product_attribute_value_id', 'in', group.attribute_ids.ids)]
            )

            data.append({
                "category_ids": categories.ids,
                "attribute_ids": attributes.ids,
                **group.read(["id", "sequence", "name"], load=None)[0]
            })

        return data

