# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.
# NOT WORKING YET
{
    'name': 'Odossey || Sale Order Payment Transaction',
    'summary': """Odossey || Sale Order Payment Transaction""",
    'author': 'Odossey',
    'website': 'odossey.com',
    'license': 'OPL-1',
    'description': """
Odossey || Sale Order Payment Transaction
==========================================

Adds a "Pagar" button on the sale order form that registers a
``payment.transaction`` against the order (instead of an
``account.payment``), and a "Pagos" tab listing the transactions
already registered on the order.
""",
    'category': 'Sales/Sales',
    'depends': ['sale', 'payment'],
    'version': '19.0.0.0.1',
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'wizard/sale_order_payment_register_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
