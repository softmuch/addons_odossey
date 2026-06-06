{
    'name': 'Odossey || POS Print Per User',
    'summary': 'Assign a preparation printer per user in POS',
    'author': 'Odossey',
    'website': 'odossey.com',
    'license': 'OPL-1',
    'category': 'Point of sale',
    'version': '18.0',
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'odossey_pos_print_per_user/static/src/overrides/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
