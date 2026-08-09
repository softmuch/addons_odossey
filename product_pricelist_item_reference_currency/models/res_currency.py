from odoo import models
from odoo.fields import Domain


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def _load_pos_data_domain(self, data, config):
        domain = super()._load_pos_data_domain(data, config)
        reference_currency_ids = [
            item["reference_currency_id"]
            for item in data["product.pricelist.item"]
            if item.get("activate_reference_currency") and item.get("reference_currency_id")
        ]
        if reference_currency_ids:
            domain = Domain.OR([domain, [("id", "in", reference_currency_ids)]])
        return domain
