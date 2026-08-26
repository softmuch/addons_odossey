from odoo import models


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'odossey.pricelist.prices.mixin']
