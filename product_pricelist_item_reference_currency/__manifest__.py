{
    "name": "Product Pricelist Item Reference Currency",
    "summary": "Define a fixed price in a reference currency and let it be "
               "converted to the pricelist currency using the currency rate. "
               "Applies in Sales and in the Point of Sale.",
    "author": "Odossey",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "category": "Sales",
    "website": "odossey.com",
    "depends": ["product", "point_of_sale"],
    "data": [
        "views/product_pricelist_item_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "product_pricelist_item_reference_currency/static/src/js/product_template.js",
        ],
    },
    "development_status": "Beta",
    "installable": True,
}