{
    'name': 'Odossey || Payment Provider: PowerTranz',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': 'PowerTranz (BAC Credomatic / FAC) Hosted Payment Page with 3-D Secure and refunds.',
    'description': """
PowerTranz payment provider
===========================
* The customer is redirected to the PowerTranz Hosted Payment Page (HPP), card data never touches Odoo.
* 3-D Secure handled by PowerTranz.
* Payment result always confirmed server-to-server (SPI Payment) and amount checked.
* Full and partial refunds from the accounting payment (Refund button).
""",
    'depends': ['payment'],
    'data': [
        'views/payment_powertranz_templates.xml',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
