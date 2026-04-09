# -*- coding: utf-8 -*-
{
    "name": "Odossey || KDS",
    "summary": "Odossey || KDS",
    "description": """Odossey || KDS""",
    'author': 'Odossey',
    'website': "odossey.com",
    "category": "Point Of Sale",
    "version": "2.7.1",
    "license": "OPL-1",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": ["point_of_sale", "pos_restaurant"],
    "data": [
        "security/ir.model.access.csv",
        "views/views.xml",
        "views/templates.xml",
        "views/kitchen_screen.xml",
        "views/menu.xml",
    ],
    "images": [
        "static/description/banner.gif",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "odossey_pos_kds/static/src/**/*",
        ],
        'web.assets_tests': [
            "odossey_pos_kds/static/tests/tours/**/*",
        ],
        "point_of_sale.printer": [
            "point_of_sale/static/src/app/printer/**/*",
            ("remove", "point_of_sale/static/src/app/printer/pos_printer_service.js"),
            "pos_epson_printer/static/src/app/**/*",
            "point_of_sale/static/src/utils.js",
            "point_of_sale/static/src/app/hardware_proxy/**/*",
            'web_editor/static/lib/html2canvas.js',
            'point_of_sale/static/src/app/utils/html-to-image.js'
        ],
    },
}
