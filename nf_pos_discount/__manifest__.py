# -*- coding: utf-8 -*-
# Copyright (C) 2021-Today: Part of NextFlowIT.
# @author:  Part of NextFlowIT.

{
    'name': 'Point Of Sale Discount || Point of sale Amount/Percentage discount ',
    'summary': """ point of sale global discount line discount apply discount base on amount pos discount amount discount global discount price discount line price discount remove discount global auto calculate discount pos global discount pos line discount pos discount """,
    'author': 'NextFlowIT',
    "license": "OPL-1",
    'description': """ apply disocunt base on amount also apply global disocunt in point of sale. """,
    'category': "Point of sale",
    'website': '',
    'depends': ['point_of_sale'],
    'version': '0.0.3',
    'data': [
        'views/res_pos_config.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'nf_pos_discount/static/src/overrides/**/*',
            'nf_pos_discount/static/src/apps/contro_buttons/controlbutton.js',
            'nf_pos_discount/static/src/apps/contro_buttons/controlbutton.xml',
            'nf_pos_discount/static/src/apps/popups/numberPopup/*',
            'nf_pos_discount/static/src/apps/models.js',
            # 'nf_pos_discount/static/src/overrides/OrderWidget/OrderWidget.xml',
        ],
    },
    "images": ["static/description/background.gif", ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
     "price": 25.42,
    'auto_install': False,
    "currency": "EUR"
}
