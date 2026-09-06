# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

from odoo import api, fields, models


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
    # Only exists so `_compute_pos_credit_balance` below has a real
    # dependency path to declare -- without one, Odoo has no way to know a
    # newly created/consumed `pos.customer.credit` row should invalidate
    # this partner's cached balance, and a stale (pre-banking or
    # pre-consumption) value can leak into a later read within the same
    # transaction (e.g. one order redistributes/banks credit and another
    # order for the same partner consumes it in the same request).
    pos_customer_credit_ids = fields.One2many('pos.customer.credit', 'partner_id')

    def _compute_pos_credit_currency_id(self):
        for partner in self:
            partner.pos_credit_currency_id = self.env.company.currency_id

    @api.depends('pos_customer_credit_ids.amount')
    def _compute_pos_credit_balance(self):
        data = self.env['pos.customer.credit']._read_group(
            domain=[('partner_id', 'in', self.ids), ('company_id', '=', self.env.company.id)],
            groupby=['partner_id'],
            aggregates=['amount:sum'],
        )
        balances = {partner.id: amount for partner, amount in data}
        for partner in self:
            partner.pos_credit_balance = balances.get(partner.id, 0.0)

    @api.model
    def _load_pos_data_fields(self, config):
        # Needed by the POS frontend touch checkout to show/gate the "Use
        # Customer Credit" checkbox (see
        # overrides/screens/payment_screen.js).
        return super()._load_pos_data_fields(config) + ['pos_credit_balance']
