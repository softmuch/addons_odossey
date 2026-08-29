# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

from odoo import api, fields, models


class SaleOrderPaymentRegister(models.TransientModel):
    _name = 'sale.order.payment.register'
    _description = 'Register a Payment Transaction on a Sale Order'

    sale_order_id = fields.Many2one('sale.order', string="Sale Order", required=True)
    partner_id = fields.Many2one(related='sale_order_id.partner_id')
    currency_id = fields.Many2one(related='sale_order_id.currency_id')
    amount = fields.Monetary(string="Amount", required=True, currency_field='currency_id')
    provider_id = fields.Many2one(
        'payment.provider', string="Payment Provider", required=True,
        domain="[('state', 'in', ('enabled', 'test'))]",
    )
    payment_method_id = fields.Many2one(
        'payment.method', string="Payment Method", required=True,
        domain="[('id', 'in', provider_id.payment_method_ids)]",
    )
    reference = fields.Char(string="Reference")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'sale_order_id' in res and 'amount' in fields_list and 'amount' not in res:
            order = self.env['sale.order'].browse(res['sale_order_id'])
            res['amount'] = order.amount_total
        return res

    def action_confirm(self):
        self.ensure_one()
        tx = self.env['payment.transaction'].sudo().create({
            'provider_id': self.provider_id.id,
            'payment_method_id': self.payment_method_id.id,
            'reference': self.reference or self.env['payment.transaction']._compute_reference(
                self.provider_id.code, prefix=self.sale_order_id.name,
            ),
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'operation': 'offline',
            'sale_order_ids': [(6, 0, [self.sale_order_id.id])],
        })
        tx._set_done()
        return {
            'name': tx.reference,
            'type': 'ir.actions.act_window',
            'res_model': 'payment.transaction',
            'view_mode': 'form',
            'res_id': tx.id,
        }
