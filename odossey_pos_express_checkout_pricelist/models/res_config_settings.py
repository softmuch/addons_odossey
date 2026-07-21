from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_checkout_mode_pricelist = fields.Boolean(
        related='pos_config_id.use_checkout_mode_pricelist', readonly=False)
    express_checkout_pricelist_id = fields.Many2one(
        related='pos_config_id.express_checkout_pricelist_id', readonly=False)
    floor_checkout_pricelist_id = fields.Many2one(
        related='pos_config_id.floor_checkout_pricelist_id', readonly=False)
