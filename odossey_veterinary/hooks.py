import json

from odoo.tools import file_open


def post_init_hook(env):
    """Reference prices of the services (ARS, 1st half 2026, Argentine veterinary councils' minimum fees) are applied
    only when the company invoices in Argentine pesos: elsewhere the clinic sets its own prices."""
    apply_ar_reference_prices(env)
    localize_product_categories(env)


# product.category.name is not translatable: the categories are named in the company's language at install time
CATEGORY_NAMES = {
    'product_category_vet': {'es': "Veterinaria", 'it': "Veterinaria"},
    'product_category_services': {'es': "Servicios", 'it': "Servizi"},
    'product_category_vaccines': {'es': "Vacunas", 'it': "Vaccini"},
    'product_category_medications': {'es': "Medicamentos", 'it': "Farmaci"},
    'product_category_antiparasitics': {'es': "Antiparasitarios", 'it': "Antiparassitari"},
    'product_category_controlled': {'es': "Psicotrópicos y estupefacientes", 'it': "Stupefacenti e psicotropi"},
    'product_category_food': {'es': "Alimentos", 'it': "Alimenti"},
    'product_category_supplies': {'es': "Insumos clínicos", 'it': "Materiale clinico"},
    'product_category_retail': {'es': "Pet shop", 'it': "Pet shop"},
}


def localize_product_categories(env, lang=None):
    if not lang:
        admin = env.ref('base.user_admin', raise_if_not_found=False)
        langs = [env.company.partner_id.lang, admin and admin.lang, env.user.lang]
        lang = next((code for code in langs if code and code[:2] in ('es', 'it')), 'en_US')
    lang = lang[:2]
    for xmlid, names in CATEGORY_NAMES.items():
        category = env.ref('odossey_veterinary.%s' % xmlid, raise_if_not_found=False)
        if category and lang in names:
            category.name = names[lang]


def apply_ar_reference_prices(env):
    if env.company.currency_id.name != 'ARS':
        return
    with file_open('odossey_veterinary/data/ar_reference_prices.json') as f:
        prices = json.load(f)
    for xmlid, price in prices.items():
        product = env.ref('odossey_veterinary.%s' % xmlid, raise_if_not_found=False)
        if product and not product.list_price:
            product.list_price = price
