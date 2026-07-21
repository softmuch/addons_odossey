{
    'name': 'Odossey || POS Express Checkout Pricelist',
    'version': '18.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Default pricelist per checkout mode: one for express checkout, one for floor (table) mode',
    'depends': ['odossey_pos_express_checkout'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'odossey_pos_express_checkout_pricelist/static/src/pos_store_patch.js',
            'odossey_pos_express_checkout_pricelist/static/src/express_checkout_pricelist.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
