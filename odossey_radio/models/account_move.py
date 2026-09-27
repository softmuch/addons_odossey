from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    radio_period_start = fields.Date(string="Advertising Period From", copy=False)
    radio_period_end = fields.Date(string="Advertising Period To", copy=False)
    radio_emission_ids = fields.One2many('radio.emission', 'invoice_id', string="Aired Spots")
    radio_commission_bill_id = fields.Many2one(
        'account.move', string="Agency Commission Bill", copy=False,
        help="Bill of the agency that settled the commission of this invoice.")


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    radio_program_id = fields.Many2one('radio.program', string="Program", index='btree_not_null')
    radio_format_id = fields.Many2one('radio.ad.format', string="Advertising Format")
    radio_daypart_id = fields.Many2one('radio.daypart', string="Daypart")
