{
    'name': 'Odossey || POS Cash Extractions',
    'version': '18.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'author': 'Odossey',
    'website': 'odossey.com',
    'summary': 'Menu to review all manual cash in/out movements made in POS sessions, grouped by day',
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_cash_extraction_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'OPL-1',
    'post_init_hook': 'post_init_hook',
}
