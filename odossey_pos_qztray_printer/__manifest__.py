{
    'name': 'Odossey POS QZ Tray Printer',
    'version': '18.0.1.0.0',
    'summary': 'Print POS receipts via QZ Tray — browser connects to local QZ Tray app which forwards to the printer (OS driver or raw TCP socket)',
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
            # qz-tray.js is loaded dynamically via loadJS in qztray_printer.js
            # to avoid UMD/CommonJS conflicts with Odoo's asset bundler
            'odossey_pos_qztray_printer/static/src/app/qztray_printer.js',
            'odossey_pos_qztray_printer/static/src/overrides/models/pos_store.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
