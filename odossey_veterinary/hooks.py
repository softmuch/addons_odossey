import json

from odoo.tools import file_open


def post_init_hook(env):
    """Reference prices of the services (ARS, 1st half 2026, Argentine veterinary councils' minimum fees) are applied
    only when the company invoices in Argentine pesos: elsewhere the clinic sets its own prices."""
    apply_ar_reference_prices(env)


def apply_ar_reference_prices(env):
    if env.company.currency_id.name != 'ARS':
        return
    with file_open('odossey_veterinary/data/ar_reference_prices.json') as f:
        prices = json.load(f)
    for xmlid, price in prices.items():
        product = env.ref('odossey_veterinary.%s' % xmlid, raise_if_not_found=False)
        if product and not product.list_price:
            product.list_price = price
