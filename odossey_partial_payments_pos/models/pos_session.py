# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

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
        default_account = self._get_balancing_account()
        return self.action_pos_session_closing_control(default_account, amount_to_balance)
