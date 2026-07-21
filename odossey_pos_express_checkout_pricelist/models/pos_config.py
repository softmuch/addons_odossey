from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    use_checkout_mode_pricelist = fields.Boolean(
        string="Pricelist by Checkout Mode",
        help="Use a different default pricelist depending on whether the order "
             "was started in Express Checkout mode or Floor (table) mode.",
    )
    express_checkout_pricelist_id = fields.Many2one(
        'product.pricelist',
        string="Express Checkout Pricelist",
        help="Default pricelist applied to orders started in Express Checkout mode.",
    )
    floor_checkout_pricelist_id = fields.Many2one(
        'product.pricelist',
        string="Floor Mode Pricelist",
        help="Default pricelist applied to orders started from the Floor (table) screen.",
    )

    @api.constrains('use_checkout_mode_pricelist', 'use_pricelist')
    def _check_use_checkout_mode_pricelist_requires_flexible_pricelists(self):
        for config in self:
            if config.use_checkout_mode_pricelist and not config.use_pricelist:
                raise ValidationError(_(
                    "You must enable 'Flexible Pricelists' (Pricing section) before "
                    "activating 'Pricelist by Checkout Mode': pricelists are not loaded "
                    "in the POS session unless that setting is on."
                ))
