from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _prepare_account_bank_statement_line_vals(self, session, sign, amount, reason, extras):
        vals = super()._prepare_account_bank_statement_line_vals(session, sign, amount, reason, extras)
        vals['is_pos_manual_cash_move'] = True
        return vals
