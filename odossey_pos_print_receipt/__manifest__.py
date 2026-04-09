{
    "name": "Odossey || Print Receipt Before Pay",
    "category": "Point of Sale",
    "summary": """Odossey || Print Receipt Before Pay""",
    "description": """Odossey || Print Receipt Before Pay""",
    "license": "OPL-1",
    'version': '18.0',
    "depends": ["point_of_sale"],
    "application": True,
    "data": ["views/res_config.xml"],
    "assets": {
        "point_of_sale._assets_pos": [
            "odossey_pos_print_receipt/static/src/overrides/app/store/pos_store.js",
            "odossey_pos_print_receipt/static/src/overrides/screens/order_receipt/order_receipt.xml",
            "odossey_pos_print_receipt/static/src/overrides/screens/product_screen/product_screen.xml",
            "odossey_pos_print_receipt/static/src/overrides/screens/product_screen/product_screen.js",
            "odossey_pos_print_receipt/static/src/overrides/screens/custom_popup/custom_popup.js",
            "odossey_pos_print_receipt/static/src/overrides/screens/custom_popup/custom_popup.xml",
        ],
    },
    'author': 'Odossey',
    'website': "odossey.com",
    "license": "OPL-1",
    'installable': True,
    'application': False,
    'auto_install': False
}
