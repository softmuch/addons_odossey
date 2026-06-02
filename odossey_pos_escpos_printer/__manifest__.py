{
    'name': 'Odossey POS ESC/POS Network Printer',
    'version': '18.0.1.0.0',
    'summary': 'Print POS receipts on ESC/POS network printers via server-side TCP proxy — no IoT Box required',
    'category': 'Point of Sale',
    'author': 'Odossey',
    'website': 'odossey.com',
    'license': 'LGPL-3',
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_printer_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'odossey_pos_escpos_printer/static/src/app/escpos_printer.js',
            'odossey_pos_escpos_printer/static/src/overrides/models/pos_store.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
