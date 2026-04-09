# -*- coding: utf-8 -*-
# Copyright (C) 2021-Today: Part of Odossey. 
# @author:  Part of Odossey. 

from odoo import models, fields, api

class ResConfigPosInherit(models.TransientModel):
    _inherit = "res.config.settings"

    nf_enbale_price_discount = fields.Boolean(related="pos_config_id.nf_enbale_price_discount", readonly=False)