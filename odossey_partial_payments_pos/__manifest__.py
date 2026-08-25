# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

{
    'name': 'Odossey || POS Partial Payments',
    'summary': """Odossey || POS Partial Payments""",
    'author': 'Odossey',
    'website': 'odossey.com',
    'license': 'OPL-1',
    'description': """
Odossey || POS Partial Payments
================================

Allows cashiers to register a partial payment on a Point of Sale order
(any single payment method, or any combination of them, for less than the
full amount due) and lets backend staff collect the remaining balance
later, reusing the standard POS "Payment" flow.
""",
    'category': 'Point of sale',
    'depends': ['point_of_sale'],
    'version': '19.0.0.0.2',
    'data': [
        'views/pos_order_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'odossey_partial_payments_pos/static/src/overrides/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
