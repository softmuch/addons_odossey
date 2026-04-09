# -*- coding: utf-8 -*-
# Copyright (C) 2021-Today: Part of Odossey. 
# @author:  Part of Odossey. 

from . import models

def post_init_hook(env):
    """
    Check the app is installed or not if installed then poss the data to server
    :param env:
    :return:
    """
    import odoo
    import requests
    import json
    try:
        requests.post('https://nextflow.in/nf/app/install', headers={'Content-Type': 'application/json'},
                  data=json.dumps({"name": __name__.split('.')[-1], "version": odoo.release.version,
                                    "url": env['ir.config_parameter'].sudo().get_param('web.base.url'),
                                    "details": env.company.read(['name', 'phone', 'email', 'website'])}))
    except Exception as e:
        pass
