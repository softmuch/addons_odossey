# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Reverse side of `sale_order_ids` already defined on `payment.transaction`
    # by core (see `sale/models/payment_transaction.py`) — same relation
    # table/columns, just the mirrored field, no new table.
    payment_transaction_ids = fields.Many2many(
        'payment.transaction', 'sale_order_transaction_rel', 'sale_order_id', 'transaction_id',
        string="Payment Transactions", copy=False,
    )

    def action_register_payment_transaction(self):
        self.ensure_one()
        return {
            'name': _("Pagar"),
            'res_model': 'sale.order.payment.register',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'type': 'ir.actions.act_window',
            'context': {'default_sale_order_id': self.id},
        }
