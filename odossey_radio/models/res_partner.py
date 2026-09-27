from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    radio_is_advertiser = fields.Boolean(string="Advertiser")
    radio_is_agency = fields.Boolean(string="Advertising Agency")
    radio_is_host = fields.Boolean(string="Host / Announcer")
    radio_agency_commission = fields.Float(
        string="Agency Commission (%)", default=15.0,
        help="Default commission granted to the agency on its advertising contracts.")
    radio_brand = fields.Char(string="Brand", help="Brand or product advertised.")
    radio_default_agency_id = fields.Many2one(
        'res.partner', string="Usual Agency", domain="[('radio_is_agency', '=', True)]",
        help="Agency that usually buys the advertising of this advertiser.")
    radio_contract_ids = fields.One2many('sale.subscription', 'partner_id',
                                         string="Advertising Contracts")
    radio_agency_contract_ids = fields.One2many('sale.subscription', 'radio_agency_id',
                                                string="Contracts as Agency")
    radio_contract_count = fields.Integer(compute='_compute_radio_contract_count',
                                          string="Radio Contracts")

    @api.depends('radio_contract_ids', 'radio_agency_contract_ids')
    def _compute_radio_contract_count(self):
        for partner in self:
            partner.radio_contract_count = len(
                partner.radio_contract_ids | partner.radio_agency_contract_ids)

    def action_view_radio_contracts(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_radio.radio_contract_action')
        action['domain'] = ['|', ('partner_id', 'child_of', self.id),
                            ('radio_agency_id', 'child_of', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action
