from markupsafe import Markup

from odoo import fields, models
from odoo.tools import formatLang


class PricelistPricesMixin(models.AbstractModel):
    _name = 'odossey.pricelist.prices.mixin'
    _description = "Show All Pricelist Prices"

    pricelist_prices_html = fields.Html(
        string="Pricelist Prices",
        compute='_compute_pricelist_prices_html',
        sanitize=False,
    )

    def _compute_pricelist_prices_html(self):
        saved_products = self.filtered('id')
        pricelists = self.env['product.pricelist'].search([]) if saved_products else self.env['product.pricelist']
        price_data = pricelists._compute_price_rule_multi(saved_products, 1.0) if pricelists else {}
        for product in self:
            if not product.id:
                product.pricelist_prices_html = False
                continue
            product_prices = price_data.get(product.id, {})
            rows = [
                Markup("<div><i>%s</i>: <b>%s</b></div>") % (
                    pricelist.name,
                    formatLang(
                        self.env,
                        product_prices.get(pricelist.id, (0.0, False))[0],
                        currency_obj=pricelist.currency_id,
                    ),
                )
                for pricelist in pricelists
            ]
            product.pricelist_prices_html = Markup('').join(rows) if rows else False
