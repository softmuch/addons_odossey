# -*- coding: utf-8 -*-
# Copyright (C) 2021-Today: Part of Odossey.
# @author:  Part of Odossey.

{
    'name': 'Odossey || POS Print Pre-Bill',
    'summary': """Odossey || POS Print Pre-Bill""",
    'author': 'Odossey',
    'website': "odossey.com",
    "license": "OPL-1",
    'description': """Odossey || POS Print Pre-Bill""",
    'category': "Point of sale",
    'depends': ['pos_restaurant', 'odossey_pos_kds'],
    'version': '18.0',
    'data': [],
    'assets': {
        'point_of_sale._assets_pos': [
            'odossey_pos_print_pre_bill/static/src/overrides/**/*',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
