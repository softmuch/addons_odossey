from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class RadioScheduleGenerate(models.TransientModel):
    _name = 'radio.schedule.generate'
    _description = "Plan the Daily Log"

    date_from = fields.Date(string="From", required=True, default=fields.Date.context_today)
    date_to = fields.Date(string="To", required=True,
                          default=lambda self: fields.Date.context_today(self) + timedelta(days=6))
    subscription_ids = fields.Many2many(
        'sale.subscription', string="Contracts",
        domain="[('radio_contract', '=', True), ('in_progress', '=', True)]",
        help="Leave empty to plan all the contracts in progress.")

    def action_generate(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(self.env._("The end date must be after the start date."))
        if (self.date_to - self.date_from).days > 92:
            raise UserError(self.env._("Plan at most three months at a time."))
        contracts = self.subscription_ids or self.env['sale.subscription'].search(
            [('radio_contract', '=', True), ('in_progress', '=', True)])
        emissions = contracts._radio_plan(self.date_from, self.date_to)
        conflicts = emissions.filtered(lambda e: e.state == 'conflict')
        message = self.env._("%(count)s spots planned.", count=len(emissions - conflicts))
        if conflicts:
            message += " " + self.env._(
                "%(count)s spots without room in the breaks (see the filter 'No room').",
                count=len(conflicts))
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_radio.radio_emission_action')
        action['domain'] = [('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        action['context'] = {'search_default_group_date': 1}
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'warning' if conflicts else 'success', 'message': message,
                       'sticky': bool(conflicts), 'next': action},
        }


class RadioCertificateWizard(models.TransientModel):
    _name = 'radio.certificate.wizard'
    _description = "Broadcast Certificate"

    subscription_id = fields.Many2one('sale.subscription', string="Contract", required=True)
    date_from = fields.Date(
        string="From", required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1) - relativedelta(months=1))
    date_to = fields.Date(
        string="To", required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1) - timedelta(days=1))
    aired_count = fields.Integer(compute='_compute_aired_count', string="Aired Spots")

    @api.depends('subscription_id', 'date_from', 'date_to')
    def _compute_aired_count(self):
        for wizard in self:
            wizard.aired_count = len(wizard.subscription_id._radio_certificate_emissions(
                wizard.date_from, wizard.date_to)) if wizard.subscription_id and \
                wizard.date_from and wizard.date_to else 0

    def action_print(self):
        self.ensure_one()
        if not self.aired_count:
            raise UserError(self.env._("There are no aired spots in the period."))
        return self.env.ref('odossey_radio.action_report_radio_certificate').with_context(
            radio_date_from=fields.Date.to_string(self.date_from),
            radio_date_to=fields.Date.to_string(self.date_to),
        ).report_action(self.subscription_id)


class RadioCommissionSettle(models.TransientModel):
    """Monthly settlement of the agency commissions (contracts with the commission invoiced
    by the agency): one draft vendor bill per agency."""
    _name = 'radio.commission.settle'
    _description = "Settle Agency Commissions"

    date_from = fields.Date(
        string="From", required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1) - relativedelta(months=1))
    date_to = fields.Date(
        string="To", required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1) - timedelta(days=1))

    def _invoices_to_settle(self):
        return self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
            ('invoice_date', '>=', self.date_from), ('invoice_date', '<=', self.date_to),
            ('subscription_id.radio_contract', '=', True),
            ('subscription_id.radio_agency_id', '!=', False),
            ('subscription_id.radio_commission_mode', '=', 'bill'),
            ('subscription_id.radio_commission', '>', 0),
            ('radio_commission_bill_id', '=', False),
        ])

    def action_settle(self):
        self.ensure_one()
        company = self.env.company
        product = company.radio_agency_commission_product_id
        if not product:
            raise UserError(self.env._(
                "Set the agency commission product in the Radio settings first."))
        invoices = self._invoices_to_settle()
        if not invoices:
            raise UserError(self.env._("There are no commissions to settle in the period."))
        by_agency = defaultdict(lambda: self.env['account.move'])
        for invoice in invoices:
            by_agency[invoice.subscription_id.radio_agency_id] |= invoice
        bills = self.env['account.move']
        account = (product.property_account_expense_id
                   or product.categ_id.property_account_expense_categ_id)
        for agency, agency_invoices in by_agency.items():
            lines = []
            for invoice in agency_invoices:
                contract = invoice.subscription_id
                values = {
                    'product_id': product.id,
                    'name': self.env._("Commission %(rate)s%% on %(invoice)s (%(advertiser)s)",
                                       rate=contract.radio_commission, invoice=invoice.name,
                                       advertiser=contract.partner_id.name),
                    'quantity': 1,
                    'price_unit': invoice.currency_id.round(
                        invoice.amount_untaxed * contract.radio_commission / 100.0),
                }
                if account:
                    values['account_id'] = account.id
                lines.append(Command.create(values))
            bill = self.env['account.move'].create({
                'move_type': 'in_invoice',
                'partner_id': agency.id,
                'invoice_date': self.date_to,
                'ref': self.env._("Agency commissions %(start)s - %(end)s",
                                  start=self.date_from, end=self.date_to),
                'invoice_line_ids': lines,
            })
            agency_invoices.write({'radio_commission_bill_id': bill.id})
            bills |= bill
        return {
            'type': 'ir.actions.act_window', 'res_model': 'account.move',
            'name': self.env._("Agency Commission Bills"),
            'view_mode': 'list,form', 'domain': [('id', 'in', bills.ids)],
            'context': {'default_move_type': 'in_invoice'},
        }
