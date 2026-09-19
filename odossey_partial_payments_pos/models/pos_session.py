# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def action_pos_session_closing_control(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        """Before closing: an order of this session that is `partially_paid`
        but actually OVERPAID (payments above its total) would have its
        excess silently netted against other customers' unpaid balances in
        the closing difference. Redistribute it first (to the customer's
        other partially paid orders, then banked as customer credit), like
        `_process_saved_order` does, so the difference left really is only
        what customers still owe."""
        for order in self.mapped('order_ids').filtered(lambda o: o.state == 'partially_paid'):
            if order.currency_id.compare_amounts(order.amount_paid, order.amount_total) > 0:
                order._redistribute_overpayment()
                order.amount_paid = order._compute_amount_paid()
                if order._is_order_paid_with_rounding():
                    order.action_pos_order_paid()
        return super().action_pos_session_closing_control(
            balancing_account, amount_to_balance, bank_payment_method_diffs
        )

    def _close_session_action(self, amount_to_balance):
        """Auto-resolve the "Force Close Session" wizard instead of showing
        it to the user.

        A `partially_paid` order (this module's own feature) is deliberately
        kept out of 'draft' so it counts towards the session's closing
        totals -- but nothing ever collects the unpaid remainder, so
        `_validate_session` (core) always finds the accounting move
        unbalanced for a session with such an order and rolls back to show
        this wizard instead of closing. Core's own wizard
        (`pos.close.session.wizard.close_session`) just replays
        `action_pos_session_closing_control` with the default balancing
        account and the computed difference -- do exactly that here,
        automatically, instead of making the user click through it.
        """
        if self.env.context.get('odossey_force_close_retry'):
            # The retry with the balancing account did not balance either:
            # do NOT loop (core rolls the whole transaction back and calls
            # this hook again each time) -- show core's own wizard.
            return super()._close_session_action(amount_to_balance)
        default_account = self._get_balancing_account()
        return self.with_context(odossey_force_close_retry=True).action_pos_session_closing_control(
            default_account, amount_to_balance
        )
