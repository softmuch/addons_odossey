from odoo import fields, models

TRAVEL_SERVICE_TYPES = [
    ('flight', "Flight"),
    ('lodging', "Lodging"),
    ('transfer', "Transfer"),
    ('ground', "Ground Services"),
    ('excursion', "Excursion"),
    ('assistance', "Travel Assistance"),
    ('commission', "Agency Services / Commission"),
    ('fee', "Payment / Bank Fees"),
    ('other', "Other"),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    travel_service_type = fields.Selection(
        selection=TRAVEL_SERVICE_TYPES, string="Travel Service Type",
        help="Classifies the product in the travel reports. On vendor bills, products of type "
             "'Payment / Bank Fees' are reported as fees instead of supplier costs.")
