{
    'name': 'Odossey || POS Confirm Order Button',
    'version': '18.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'author': 'Odossey',
    'website': 'odossey.com',
    'summary': 'Button to force-confirm orders stuck open after a printer error',
    'depends': ['pos_restaurant'],
    'data': [],
    'installable': True,
    'application': False,
    'license': 'OPL-1',
    'assets': {
        'point_of_sale._assets_pos': [
            'odossey_pos_confirm_button/static/src/js/ConfirmOrderButton.js',
            'odossey_pos_confirm_button/static/src/xml/ConfirmOrderButton.xml',
        ],
    },
}
