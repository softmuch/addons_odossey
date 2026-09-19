# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

from odoo import _, fields, models
from odoo.tools import float_is_zero


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    def _create_late_account_payments(self):
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
