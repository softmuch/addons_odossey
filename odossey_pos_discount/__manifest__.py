# -*- coding: utf-8 -*-
# Copyright (C) 2021-Today: Part of Odossey.
# @author:  Part of Odossey.

{
    'name': 'Odossey || POS Discount',
    'summary': """Odossey || POS Discount""",
    'author': 'Odossey',
    'website': "odossey.com",
    "license": "OPL-1",
    'description': """Odossey || POS Discount""",
    'category': "Point of sale",
    'depends': ['point_of_sale'],
    'version': '0.0.3',
    'data': [
        'views/res_pos_config.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'odossey_pos_discount/static/src/overrides/**/*',
            'odossey_pos_discount/static/src/apps/contro_buttons/controlbutton.js',
            'odossey_pos_discount/static/src/apps/contro_buttons/controlbutton.xml',
            'odossey_pos_discount/static/src/apps/popups/numberPopup/*',
            'odossey_pos_discount/static/src/apps/models.js',
            # 'odossey_pos_discount/static/src/overrides/OrderWidget/OrderWidget.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
