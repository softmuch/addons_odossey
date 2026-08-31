from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    pos_extract_cash = fields.Boolean(
        string="Extraer de caja",
        help="Al confirmar la orden se generará una salida de efectivo por el importe total "
             "de la orden en la sesión POS seleccionada.",
    )
    pos_session_id = fields.Many2one(
        'pos.session', string="Sesión POS",
        domain=[('state', '=', 'opened')],
        help="Sesión POS abierta de la que se extraerá el efectivo al confirmar la orden.",
    )
    pos_cash_move_id = fields.Many2one(
        'account.bank.statement.line', string="Salida de caja generada",
        readonly=True, copy=False,
    )
    has_open_pos_session = fields.Boolean(compute='_compute_has_open_pos_session')

    @api.depends('company_id')
    def _compute_has_open_pos_session(self):
        open_by_company = {}
        for order in self:
            company_id = order.company_id.id
            if company_id not in open_by_company:
                open_by_company[company_id] = bool(self.env['pos.session'].search_count([
                    ('state', '=', 'opened'),
                    ('company_id', '=', company_id),
                ]))
            order.has_open_pos_session = open_by_company[company_id]

    @api.onchange('pos_extract_cash')
    def _onchange_pos_extract_cash(self):
        if not self.pos_extract_cash:
            self.pos_session_id = False
            return
        open_sessions = self.env['pos.session'].search([
            ('state', '=', 'opened'),
            ('company_id', '=', self.company_id.id),
        ])
        if len(open_sessions) == 1:
            self.pos_session_id = open_sessions

    @api.constrains('pos_extract_cash', 'pos_session_id')
    def _check_pos_extract_cash_session(self):
        for order in self:
            if order.pos_extract_cash and not order.pos_session_id:
                raise ValidationError(_(
                    "Seleccioná una sesión POS abierta de la que extraer el efectivo, "
                    "o destildá 'Extraer de caja'."
                ))

    def button_approve(self, force=False):
        res = super().button_approve(force=force)
        self.filtered(
            lambda o: o.state == 'purchase' and o.pos_extract_cash and o.pos_session_id and not o.pos_cash_move_id
        )._create_pos_cash_extraction()
        return res

    def _get_pos_cash_extraction_reason(self):
        self.ensure_one()
        parts = []
        for line in self.order_line.filtered(lambda l: not l.display_type):
            code = line.product_id.default_code
            parts.append(f"[{code}] {line.product_id.name}" if code else line.product_id.name)
        return "; ".join(parts)

    def _create_pos_cash_extraction(self):
        for order in self:
            session = order.pos_session_id
            if session.state != 'opened':
                raise UserError(_(
                    "La sesión POS %(session)s ya no está abierta. "
                    "Seleccioná otra sesión abierta para extraer el efectivo de la orden %(order)s.",
                    session=session.name, order=order.name,
                ))
            if not session.cash_journal_id:
                raise UserError(_(
                    "La sesión POS %s no tiene un método de pago en efectivo configurado.",
                    session.name,
                ))
            reason = order._get_pos_cash_extraction_reason()
            vals = session._prepare_account_bank_statement_line_vals(
                session, -1, order.amount_total, reason,
                {'translatedType': _("Salida de caja")},
            )
            move = self.env['account.bank.statement.line'].sudo().create(vals)
            order.pos_cash_move_id = move.id
