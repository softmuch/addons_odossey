# -*- coding: utf-8 -*-
# Copyright (C) 2021-Today: Part of Odossey.
# @author:  Part of Odossey.

{
    'name': 'Odossey || Invoice Digitization with Claude',
    'summary': """Digitize vendor bills (PDF / images) with Claude AI and confirm the data in a review wizard""",
    'author': 'Odossey',
    'website': "odossey.com",
    "license": "OPL-1",
    'description': """
Odossey || Invoice Digitization with Claude
===========================================
Reads vendor bills (PDF, JPG, PNG, WEBP, GIF) with the Claude API and shows a
confirmation wizard: every datum read is placed on its invoice field, and the
data Claude could not place are listed at the bottom so the user decides where
they go. On confirmation the data are written into a draft vendor bill.
""",
    'category': "Accounting/Accounting",
    'depends': ['account'],
    'version': '20.0.1.0.0',
    'data': [
        'security/ir.access.csv',
        'wizard/claude_invoice_wizard_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'external_dependencies': {'python': ['requests']},
    'installable': True,
    'application': False,
    'auto_install': False,
}
