# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # res.partner has no currency field of its own to hang a Monetary field
    # off of -- this just mirrors the current company's currency so the
    # amount below renders correctly.
    pos_credit_currency_id = fields.Many2one(
        'res.currency', compute='_compute_pos_credit_currency_id'
    )
    pos_credit_balance = fields.Monetary(
        compute='_compute_pos_credit_balance',
        currency_field='pos_credit_currency_id',
        string='POS Credit Balance',
    )

    def _compute_pos_credit_currency_id(self):
        for partner in self:
            partner.pos_credit_currency_id = self.env.company.currency_id

    def _compute_pos_credit_balance(self):
        data = self.env['pos.customer.credit']._read_group(
            domain=[('partner_id', 'in', self.ids), ('company_id', '=', self.env.company.id)],
            groupby=['partner_id'],
            aggregates=['amount:sum'],
        )
        balances = {partner.id: amount for partner, amount in data}
        for partner in self:
            partner.pos_credit_balance = balances.get(partner.id, 0.0)
