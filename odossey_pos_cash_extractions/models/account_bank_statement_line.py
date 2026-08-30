from odoo import api, fields, models


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    is_pos_manual_cash_move = fields.Boolean(
        string='Manual POS Cash Move',
        default=False,
        help="Set on lines created from the POS 'Cash In/Out' button, "
             "to tell them apart from closing-difference and order-payment lines.",
    )
    is_pos_closing_diff = fields.Boolean(
        string='POS Closing Difference',
        default=False,
        help="Set on the cash difference (loss/profit) line created when closing a POS session.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        # _post_statement_difference() (pos_session.py) has no _prepare_* hook to override,
        # so we tag it here using the same 'counterpart_account_id' hack the base create()
        # reads and pops (account_bank_statement_line.py), before it disappears.
        for vals in vals_list:
            if not vals.get('pos_session_id') or not vals.get('counterpart_account_id'):
                continue
            journal = self.env['account.journal'].browse(vals.get('journal_id'))
            if vals['counterpart_account_id'] in (
                journal.loss_account_id.id,
                journal.profit_account_id.id,
            ):
                vals['is_pos_closing_diff'] = True
        return super().create(vals_list)
