import json

from odoo.tools import file_open


def post_init_hook(env):
    """Indicative private prices (ARS, October 2026) are applied only when the company invoices in Argentine pesos;
    product categories are named in the language of the clinic (product.category.name is not translatable)."""
    apply_ar_reference_prices(env)
    localize_product_categories(env)


CATEGORY_NAMES = {
    'product_category_oph': {'es': "Oftalmología", 'it': "Oculistica"},
    'product_category_consultations': {'es': "Consultas", 'it': "Visite"},
    'product_category_studies': {'es': "Estudios", 'it': "Esami strumentali"},
    'product_category_surgery': {'es': "Cirugías y procedimientos", 'it': "Interventi e procedure"},
    'product_category_medications': {'es': "Medicamentos", 'it': "Farmaci"},
    'product_category_iol': {'es': "Lentes intraoculares", 'it': "Lenti intraoculari"},
    'product_category_supplies': {'es': "Insumos quirúrgicos", 'it': "Materiale chirurgico"},
}


def localize_product_categories(env, lang=None):
    if not lang:
        admin = env.ref('base.user_admin', raise_if_not_found=False)
        langs = [env.company.partner_id.lang, admin and admin.lang, env.user.lang]
        lang = next((code for code in langs if code and code[:2] in ('es', 'it')), 'en_US')
    lang = lang[:2]
    for xmlid, names in CATEGORY_NAMES.items():
        category = env.ref('odossey_ophthalmology.%s' % xmlid, raise_if_not_found=False)
        if category and lang in names:
            category.name = names[lang]


def apply_ar_reference_prices(env):
    if env.company.currency_id.name != 'ARS':
        return
    with file_open('odossey_ophthalmology/data/ar_reference_prices.json') as f:
        prices = json.load(f)
    for xmlid, price in prices.items():
        product = env.ref('odossey_ophthalmology.%s' % xmlid, raise_if_not_found=False)
        if product and product.list_price <= 1:  # untouched default price
            product.list_price = price
