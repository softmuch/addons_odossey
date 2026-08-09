{
    'name': 'Odossey || POS Show Price',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'author': 'Odossey',
    'website': 'odossey.com',
    'summary': 'Show product price on the ProductScreen grid cards',
    'depends': ['point_of_sale'],
    'data': [],
    'installable': True,
    'application': False,
    'license': 'OPL-1',
    'assets': {
        'point_of_sale._assets_pos': [
            'odossey_pos_show_price/static/src/js/ProductCard.js',
            'odossey_pos_show_price/static/src/js/ProductScreen.js',
            'odossey_pos_show_price/static/src/xml/ProductCard.xml',
            'odossey_pos_show_price/static/src/xml/ProductScreen.xml',
            'odossey_pos_show_price/static/src/scss/product_card.scss',
        ],
    },
}
