# License OPL-1
from odoo import fields, models


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

    def _compute_pos_supplier_credit_currency_id(self):
        for partner in self:
            partner.pos_supplier_credit_currency_id = self.env.company.currency_id

    def _compute_pos_supplier_credit_balance(self):
        data = self.env['pos.supplier.credit']._read_group(
            domain=[('partner_id', 'in', self.ids), ('company_id', '=', self.env.company.id)],
            groupby=['partner_id'],
            aggregates=['amount:sum'],
        )
        balances = {partner.id: amount for partner, amount in data}
        for partner in self:
            partner.pos_supplier_credit_balance = balances.get(partner.id, 0.0)
