# -*- coding: utf-8 -*-
{
    "name": "POS Kitchen Screen",
    "summary": "The POS Kitchen Screen module streamlines kitchen operations with real-time order updates, status tracking, and efficient order management. Real-time sync, Preparation display, POS order sync, Kitchen display, POS kitchen display, Odoo Kitchen Display, Point of sale restaurant screen, POS restaurant, Kitchen Order print, Kitchen print, Preparation Time, Order changes, internal notes, notification sound, Odoo KDS, Odoo kitchen order management, Digital kitchen screen Odoo, Odoo kitchen management software, Odoo kitchen workflow management, Streamline kitchen orders with Odoo KDS, Real-time kitchen order tracking Odoo, Best Odoo kitchen display system, Easy to use Odoo kitchen management",
    "description": """The POS Kitchen Screen module is designed to enhance kitchen efficiency by providing real-time order synchronization, allowing staff to see the latest updates instantly. With a responsive design, it ensures optimal viewing on any device. The module tracks order states from 'Cooking' to 'Ready' and 'Done', giving clear progress indicators. It also offers an overview of all food items to be cooked, helping prioritize tasks. Additionally, orders can be filtered by product category and floor, ensuring streamlined and organized kitchen operations.""",
    "author": "Andreas Bichinger",
    "support": "andreas.bichinger@gmail.com",
    "currency": "EUR",
    "price": 129.90,
    # "website": "https://www.github.com/abichinger",
    "live_test_url": "https://odoo-demo.duckdns.org/web#action=point_of_sale.action_pos_config_kanban",
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
            "abichinger_kitchen_screen/static/src/**/*",
        ],
        'web.assets_tests': [
            "abichinger_kitchen_screen/static/tests/tours/**/*",
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
