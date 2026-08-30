def post_init_hook(env):
    """Flag pre-existing POS statement lines created before this module was installed.

    Neither the manual cash-in/out nor the closing-difference line stores its counterpart
    account directly (it's only a transient create() vals key, see account_bank_statement_line.py),
    so historical lines are told apart by inspecting the actual counterpart move line's account:
    - manual cash in/out -> falls back to the cash journal's suspense account
    - closing difference (loss/profit) -> the journal's loss_account_id / profit_account_id
    - order-payment lines -> a receivable account (left untouched, not our concern here)
    """
    lines = env['account.bank.statement.line'].search([
        ('pos_session_id', '!=', False),
        ('is_pos_manual_cash_move', '=', False),
        ('is_pos_closing_diff', '=', False),
    ])
    for line in lines:
        journal = line.journal_id
        move_accounts = line.move_id.line_ids.account_id
        if journal.suspense_account_id and journal.suspense_account_id in move_accounts:
            line.is_pos_manual_cash_move = True
        elif (journal.loss_account_id and journal.loss_account_id in move_accounts) or \
                (journal.profit_account_id and journal.profit_account_id in move_accounts):
            line.is_pos_closing_diff = True
