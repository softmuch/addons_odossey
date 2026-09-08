from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import formatLang


class PosCloseSessionBackendWizard(models.TransientModel):
    _name = 'pos.close.session.backend.wizard'
    _description = 'Close POS Session from Backend'

    session_id = fields.Many2one('pos.session', required=True, readonly=True)
    cash_control = fields.Boolean(related='session_id.config_id.cash_control', readonly=True)
    currency_id = fields.Many2one(related='session_id.currency_id', readonly=True)
    counted_cash = fields.Monetary(string='Efectivo contado')
    closing_notes = fields.Text(string='Nota de cierre')
    closing_info = fields.Text(string='Resumen de cierre', compute='_compute_closing_info')

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        session_id = self.env.context.get('default_session_id')
        if session_id and 'counted_cash' in fields_list:
            session = self.env['pos.session'].browse(session_id)
            res['counted_cash'] = session.cash_register_balance_end
        return res

    @api.depends('counted_cash', 'session_id')
    def _compute_closing_info(self):
        for wizard in self:
            wizard.closing_info = wizard._build_closing_info()

    def _build_closing_info(self):
        self.ensure_one()
        if not self.session_id:
            return ''

        def fmt(amount):
            return formatLang(self.env, amount, currency_obj=self.currency_id)

        data = self.session_id.get_closing_control_data()
        orders = data['orders_details']
        lines = [_('Órdenes: %(qty)s (%(amount)s)') % {
            'qty': orders['quantity'],
            'amount': fmt(orders['amount']),
        }, '']

        cash = data['default_cash_details']
        if cash:
            moves_total = sum(move['amount'] for move in cash['moves'])
            lines += [
                _('Efectivo (%s)') % cash['name'],
                _('  Apertura: %s') % fmt(cash['opening']),
                _('  Pagos en efectivo: %s') % fmt(cash['payment_amount']),
                _('  Entrada/salida de efectivo: %s') % fmt(moves_total),
                _('  Esperado: %s') % fmt(cash['amount']),
            ]
            if self.cash_control:
                lines += [
                    _('  Contado: %s') % fmt(self.counted_cash),
                    _('  Diferencia: %s') % fmt(self.counted_cash - cash['amount']),
                ]
            lines.append('')

        for pm in data['non_cash_payment_methods']:
            lines.append(_('%(name)s: %(amount)s (%(number)s pagos)') % {
                'name': pm['name'],
                'amount': fmt(pm['amount']),
                'number': pm['number'],
            })

        return '\n'.join(lines).strip()

    def action_confirm(self):
        self.ensure_one()
        session = self.session_id
        if session.state == 'closed':
            raise UserError(_('This session is already closed.'))

        if self.cash_control:
            response = session.post_closing_cash_details(self.counted_cash)
            if not response.get('successful'):
                raise UserError(response.get('message') or _('Could not close the session.'))

        session.update_closing_control_state_session(self.closing_notes)

        result = session.action_pos_session_closing_control()
        if isinstance(result, dict):
            # Accounting imbalance: hand off to the standard closing wizard
            # (pos.close.session.wizard) so the user can resolve it manually.
            return result
        return {'type': 'ir.actions.act_window_close'}
