# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

from odoo import _, api, fields, models
from odoo.tools import float_is_zero


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    @api.constrains('amount')
    def _check_amount(self):
        """Core refuses any payment on an invoiced order. An order invoiced
        while partially paid still has a balance to collect: its remaining
        payments are allowed (they get reconciled with the invoice, see
        `_account_payments_of_invoiced_orders`)."""
        for payment in self:
            order = payment.pos_order_id
            if order.state == 'partially_paid' and order.account_move:
                continue
            super(PosPayment, payment)._check_amount()

    def _account_payments_of_invoiced_orders(self):
        """Payments added to an order that is ALREADY invoiced (invoiced
        while partially paid): book each one the way the invoicing itself
        does (`_generate_pos_order_invoice`) and reconcile it with the
        invoice. Cheques keep their own deferred flow (their payment move
        creation returns nothing here)."""
        for order, payments in self.grouped('pos_order_id').items():
            invoice = order.account_move
            payments = payments.filtered(
                lambda p: not p.account_move_id and p.payment_method_id.type != 'pay_later' and p.amount
            )
            if not invoice or not payments:
                continue
            closed = order.session_id.state == 'closed'
            moves = payments._create_payment_moves(closed)
            if not moves:
                continue
            order._reconcile_invoice_payments(invoice, moves)
            if closed:
                order._create_misc_reversal_move(moves)

    def _create_late_account_payments(self):
        self._account_payments_of_invoiced_orders()
        """Book money collected AFTER its POS session was closed.

        A `pos.payment` only reaches the books through the session closing
        entry (or, for an invoiced order, `_create_payment_moves`). A payment
        registered later on an order of an already-closed session -- from the
        backend `pos.make.payment` wizard or "Pagar Libremente" -- on an order
        that is not invoiced would therefore never generate any entry at all.
        This books it as a real, posted inbound `account.payment` on the
        payment method's journal, whose counterpart is the POS receivable
        account (where the closing entry left that order's unpaid balance),
        and links it through `account_move_id`.

        Only meant for payments created just now: earlier payments of a
        closed session are already inside its closing entry.
        """
        for payment in self:
            order = payment.pos_order_id
            method = payment.payment_method_id
            company = order.company_id
            if (
                not order
                or order.session_id.state != 'closed'
                or order.account_move
                or payment.account_move_id
                or payment.is_change
                or method.type == 'pay_later'
                or not method.journal_id
                # Cheques are accounted separately (l10n_latam_check_ext).
                or method.payment_method_type == 'check'
                or payment.amount <= 0
                or float_is_zero(payment.amount, precision_rounding=order.currency_id.rounding)
            ):
                continue
            receivable = company.account_default_pos_receivable_account_id
            account_payment = self.env['account.payment'].sudo().with_company(company).create({
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': order.partner_id.id,
                'amount': payment.amount,
                'currency_id': payment.currency_id.id,
                'journal_id': method.journal_id.id,
                'date': payment.payment_date or fields.Date.context_today(order),
                'memo': _('%(order)s (late payment, session %(session)s already closed)',
                          order=order.name, session=order.session_id.name),
                'destination_account_id': receivable.id,
            })
            account_payment.action_post()
            payment.account_move_id = account_payment.move_id[:1].id
