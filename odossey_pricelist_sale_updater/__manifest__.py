{
    'name': 'Odossey || Pricelist Sale Bulk Updater',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'author': 'Odossey',
    'website': 'odossey.com',
    'summary': 'Bulk update pricelist item prices via Excel export/import',
    'depends': ['odossey_pricelist_sale'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/pricelist_bulk_update_wizard_views.xml',
        'views/product_pricelist_item_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
}
