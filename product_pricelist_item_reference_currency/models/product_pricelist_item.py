from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import formatLang


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    activate_reference_currency = fields.Boolean(
        string="Use Reference Currency",
        help="If enabled, the Fixed Price is expressed in the Reference "
        "Currency below instead of the pricelist currency. It is "
        "automatically converted to the pricelist currency (using the "
        "reference currency's rate) whenever this pricelist item is used.",
    )
    reference_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Reference Currency",
        help="Currency in which the Fixed Price is expressed. The price is "
        "converted to the pricelist currency based on this currency's "
        "rate at computation time.",
    )
    fixed_price_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Fixed Price Currency",
        compute="_compute_fixed_price_currency_id",
        help="Technical field: currency used to display/edit the Fixed "
        "Price field (the Reference Currency when enabled, otherwise the "
        "pricelist currency).",
    )

    @api.depends("activate_reference_currency", "reference_currency_id", "currency_id")
    def _compute_fixed_price_currency_id(self):
        for item in self:
            item.fixed_price_currency_id = (
                item.reference_currency_id
                if item.activate_reference_currency and item.reference_currency_id
                else item.currency_id
            )

    @api.depends("activate_reference_currency", "reference_currency_id")
    def _compute_price_label(self):
        super()._compute_price_label()
        for item in self:
            if (
                item.compute_price == "fixed"
                and item.activate_reference_currency
                and item.reference_currency_id
            ):
                item.price = formatLang(
                    item.env,
                    item.fixed_price,
                    dp="Product Price",
                    currency_obj=item.reference_currency_id,
                )

    @api.onchange("activate_reference_currency")
    def _onchange_activate_reference_currency(self):
        for item in self:
            if not item.activate_reference_currency:
                item.reference_currency_id = False

    @api.constrains("compute_price", "activate_reference_currency", "reference_currency_id")
    def _check_reference_currency_id(self):
        for item in self:
            if (
                item.compute_price == "fixed"
                and item.activate_reference_currency
                and not item.reference_currency_id
            ):
                raise ValidationError(
                    _(
                        "Please set a Reference Currency, or disable "
                        '"Use Reference Currency" on %(item)s.',
                        item=item.display_name,
                    )
                )

    def _load_pos_data_fields(self, config):
        params = super()._load_pos_data_fields(config)
        return params + ["activate_reference_currency", "reference_currency_id"]

    def _compute_price(self, product, quantity, uom, date, currency=None, **kwargs):
        self and self.ensure_one()
        if (
            self
            and self.compute_price == "fixed"
            and self.activate_reference_currency
            and self.reference_currency_id
        ):
            product.ensure_one()
            uom.ensure_one()

            target_currency = currency or self.currency_id or self.env.company.currency_id
            target_currency.ensure_one()

            product_uom = product.uom_id
            if product_uom != uom:
                fixed_price = product_uom._compute_price(self.fixed_price, uom)
            else:
                fixed_price = self.fixed_price

            return self.reference_currency_id._convert(
                fixed_price, target_currency, self.env.company, date, round=False,
            )

        return super()._compute_price(
            product, quantity, uom, date, currency=currency, **kwargs
        )
