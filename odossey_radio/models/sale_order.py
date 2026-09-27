from datetime import timedelta

from odoo import api, fields, models


class SaleOrder(models.Model):
    """Advertising order (orden de publicidad): once confirmed it becomes a recurring
    advertising contract (subscription) that plans the daily log and invoices monthly."""
    _inherit = 'sale.order'

    radio_order = fields.Boolean(compute='_compute_radio_order', store=True, string="Radio Order")
    radio_campaign = fields.Char(string="Advertising Campaign")
    radio_brand = fields.Char(string="Brand / Product")
    radio_op_number = fields.Char(string="Advertising Order No.")
    radio_date_start = fields.Date(string="Airing Start")
    radio_date_end = fields.Date(string="Airing End",
                                 help="Leave empty for an open contract (e.g. sponsorships).")
    radio_agency_id = fields.Many2one('res.partner', string="Agency",
                                      domain="[('radio_is_agency', '=', True)]")
    radio_bill_to = fields.Selection(
        selection=[('advertiser', "Advertiser"), ('agency', "Agency")], string="Invoice To",
        default='advertiser')
    radio_commission = fields.Float(string="Agency Commission (%)")
    radio_commission_mode = fields.Selection(
        selection=[('discount', "Discount on the invoice"), ('bill', "Agency commission bill")],
        string="Commission", default='discount')
    radio_is_barter = fields.Boolean(string="Barter")
    radio_barter_note = fields.Text(string="Barter Counterpart")
    radio_is_official = fields.Boolean(string="Official Advertising")
    radio_official_body = fields.Char(string="Public Body")
    radio_seconds_per_day = fields.Integer(compute='_compute_radio_seconds',
                                           string="Seconds per Day")

    @api.depends('order_line.product_id.radio_ok')
    def _compute_radio_order(self):
        for order in self:
            order.radio_order = any(order.order_line.product_id.mapped('radio_ok'))

    @api.depends('order_line.radio_duration', 'order_line.radio_spots_per_day')
    def _compute_radio_seconds(self):
        for order in self:
            order.radio_seconds_per_day = sum(
                line.radio_duration * line.radio_spots_per_day
                for line in order.order_line.filtered('radio_line'))

    @api.onchange('radio_agency_id')
    def _onchange_radio_agency_id(self):
        self.radio_commission = self.radio_agency_id.radio_agency_commission if \
            self.radio_agency_id else 0.0
        if not self.radio_agency_id:
            self.radio_bill_to = 'advertiser'

    @api.onchange('partner_id')
    def _onchange_radio_partner(self):
        partner = self.partner_id.commercial_partner_id
        if partner.radio_default_agency_id and not self.radio_agency_id:
            self.radio_agency_id = partner.radio_default_agency_id
            self._onchange_radio_agency_id()
        if partner.radio_brand and not self.radio_brand:
            self.radio_brand = partner.radio_brand

    def _radio_contract_values(self):
        self.ensure_one()
        return {
            'radio_contract': True,
            'radio_campaign': self.radio_campaign,
            'radio_brand': self.radio_brand,
            'radio_op_number': self.radio_op_number or self.client_order_ref,
            'radio_agency_id': self.radio_agency_id.id,
            'radio_bill_to': self.radio_bill_to or 'advertiser',
            'radio_commission': self.radio_commission,
            'radio_commission_mode': self.radio_commission_mode or 'discount',
            'radio_is_barter': self.radio_is_barter,
            'radio_barter_note': self.radio_barter_note,
            'radio_is_official': self.radio_is_official,
            'radio_official_body': self.radio_official_body,
            'user_id': self.user_id.id,
            'crm_team_id': self.team_id.id,
            'fiscal_position_id': self.fiscal_position_id.id,
        }

    def action_confirm(self):
        before = {order.id: order.subscription_ids for order in self}
        res = super().action_confirm()
        for order in self.filtered('radio_order'):
            contracts = order.subscription_ids - before.get(order.id, self.env['sale.subscription'])
            for contract in contracts.filtered(lambda c: c.template_id.radio_template):
                values = order._radio_contract_values()
                start = order.radio_date_start or fields.Date.context_today(self)
                contract.write(values)
                # the end date is recomputed from the start date: write it last
                contract.write({'date_start': start})
                if order.radio_date_end:
                    contract.write({'date': order.radio_date_end})
                # fixed fee: invoiced at the start of each period; aired spots: at its end
                contract.recurring_next_date = (
                    start + contract._radio_step()
                    if contract.template_id.radio_billing_basis == 'aired' else start)
                days = contract.company_id.radio_schedule_days or 7
                today = fields.Date.context_today(self)
                contract._radio_plan(max(start, today), max(start, today) + timedelta(days=days))
        return res


class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'radio.schedule.mixin']

    def get_subscription_line_values(self):
        values = super().get_subscription_line_values()
        if self.radio_line:
            values.update(self.env['sale.subscription']._radio_line_values(self))
        return values

    @api.onchange('radio_spots_per_day', 'radio_weekday_ids', 'product_id')
    def _onchange_radio_estimate(self):
        if self.radio_line:
            self.product_uom_qty = self._radio_monthly_estimate(1)
