# License OPL-1
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    pos_supplier_credit_currency_id = fields.Many2one(
        'res.currency', compute='_compute_pos_supplier_credit_currency_id'
    )
    pos_supplier_credit_balance = fields.Monetary(
        compute='_compute_pos_supplier_credit_balance',
        currency_field='pos_supplier_credit_currency_id',
        string='Supplier Credit Balance',
    )
    # See the matching field on odossey_partial_payments_pos's res.partner
    # override -- same reasoning: gives the compute below a real dependency
    # path so a same-transaction bank-then-consume doesn't read a stale
    # cached balance.
    pos_supplier_credit_ids = fields.One2many('pos.supplier.credit', 'partner_id')

    def _compute_pos_supplier_credit_currency_id(self):
        for partner in self:
            partner.pos_supplier_credit_currency_id = self.env.company.currency_id

    @api.depends('pos_supplier_credit_ids.amount')
    def _compute_pos_supplier_credit_balance(self):
        data = self.env['pos.supplier.credit']._read_group(
            domain=[('partner_id', 'in', self.ids), ('company_id', '=', self.env.company.id)],
            groupby=['partner_id'],
            aggregates=['amount:sum'],
        )
        balances = {partner.id: amount for partner, amount in data}
        for partner in self:
            partner.pos_supplier_credit_balance = balances.get(partner.id, 0.0)
