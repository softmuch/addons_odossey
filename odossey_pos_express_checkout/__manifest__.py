{
    'name': 'Odossey || POS Express Checkout',
    'version': '18.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Quick Checkout mode: skip table selector, green navbar, return to new order after payment',
    'depends': ['pos_restaurant'],
    'assets': {
        'point_of_sale._assets_pos': [
            'odossey_pos_express_checkout/static/src/express_navbar.xml',
            'odossey_pos_express_checkout/static/src/express_navbar.js',
            'odossey_pos_express_checkout/static/src/express_receipt.js',
            'odossey_pos_express_checkout/static/src/express_checkout.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
