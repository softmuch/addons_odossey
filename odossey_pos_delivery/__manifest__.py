{
    'name': 'Odossey || POS Delivery',
    'version': '18.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Gestión de pedidos delivery para restaurantes',
    'depends': ['point_of_sale', 'pos_restaurant', 'odossey_pos_kds'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'odossey_pos_delivery/static/src/**/*',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}