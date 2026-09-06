# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

from odoo import fields, models


class PosCustomerCredit(models.Model):
    _name = 'pos.customer.credit'
    _description = 'Customer POS Credit Ledger'
    _order = 'date desc, id desc'

    partner_id = fields.Many2one('res.partner', required=True, index=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related='company_id.currency_id')
    # Positive: credit banked (an order's overpayment left over after
    # covering the customer's other partially-paid orders). Negative:
    # credit consumed (applied toward a new order's payment).
    amount = fields.Monetary(required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    origin_order_id = fields.Many2one(
        'pos.order', string='From Order',
        help='Order whose overpayment generated this credit (set when amount > 0).',
    )
    used_order_id = fields.Many2one(
        'pos.order', string='Applied To Order',
        help='Order this credit was used to pay (set when amount < 0).',
    )
