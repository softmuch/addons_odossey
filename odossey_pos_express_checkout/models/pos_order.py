from odoo import models, fields


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # Stored so a pending express order is found again after a POS reload
    # (a JS-only flag was lost, leaving the draft order orphaned).
    is_express_checkout = fields.Boolean(string='Is Express Checkout', default=False)
