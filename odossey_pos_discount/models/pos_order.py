# -*- coding: utf-8 -*-
# Copyright (C) 2021-Today: Part of Odossey. 
# @author:  Part of Odossey. 

from odoo import models, fields, api

class PosOrder(models.Model):
    _inherit = 'pos.order'

    nf_global_discoount = fields.Float(string="Global Discount")