import base64
import logging
from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from .radio_schedule_mixin import RADIO_LINE_FIELDS

_logger = logging.getLogger(__name__)


class SaleSubscriptionTemplate(models.Model):
    _inherit = 'sale.subscription.template'

    radio_template = fields.Boolean(string="Radio Advertising Contract")
    radio_billing_basis = fields.Selection(
        selection=[('fixed', "Fixed fee (in advance)"), ('aired', "Aired spots (in arrears)")],
        string="Radio Billing", default='fixed',
        help="Fixed fee: the quantities of the contract are invoiced at the beginning of each "
             "period. Aired spots: at the end of each period the spots actually aired are "
             "invoiced.")
    radio_attach_certificate = fields.Boolean(
        string="Attach Broadcast Certificate", default=True,
        help="Attach the broadcast certificate of the period to each invoice.")


class SaleSubscriptionLine(models.Model):
    _name = 'sale.subscription.line'
    _inherit = ['sale.subscription.line', 'radio.schedule.mixin']

    radio_emission_ids = fields.One2many('radio.emission', 'subscription_line_id',
                                         string="Airings")

    def _radio_airs_on(self, day):
        self.ensure_one()
        contract = self.sale_subscription_id
        if contract.date_start and day < contract.date_start:
            return False
        if contract.date and day > contract.date:
            return False
        if self.radio_date_from and day < self.radio_date_from:
            return False
        if self.radio_date_to and day > self.radio_date_to:
            return False
        return day.weekday() in self._radio_weekday_codes()

    def _radio_candidate_breaks(self, day, programs):
        """Breaks where the line can air on `day`, by time."""
        self.ensure_one()
        if self.radio_break_id:
            return self.radio_break_id.filtered(lambda b: b.program_id._airs_on(day))
        airing = programs.filtered(lambda p: p._airs_on(day))
        if self.radio_program_id:
            airing = airing & self.radio_program_id
        breaks = airing.break_ids
        if self.radio_daypart_id and not self.radio_program_id:
            breaks = breaks.filtered(lambda b: self.radio_daypart_id._contains(b.time))
        return breaks.sorted('time')

    def _prepare_account_move_line(self):
        values = super()._prepare_account_move_line()
        if self.radio_line:
            values.update({
                'radio_program_id': self.radio_program_id.id,
                'radio_format_id': self.radio_format_id.id,
                'radio_daypart_id': self.radio_daypart_id.id,
            })
            plan = self._radio_plan_description()
            if plan:
                values['name'] = f"{values['name']}\n{plan}"
        return values

    @api.onchange('radio_spots_per_day', 'radio_weekday_ids', 'product_id')
    def _onchange_radio_estimate(self):
        template = self.sale_subscription_id.template_id
        if self.radio_line and template.radio_billing_basis != 'aired':
            months = (template.recurring_interval if template.recurring_rule_type == 'months'
                      else 12 * template.recurring_interval
                      if template.recurring_rule_type == 'years' else 1)
            self.product_uom_qty = self._radio_monthly_estimate(months or 1)


class SaleSubscription(models.Model):
    _inherit = 'sale.subscription'

    radio_contract = fields.Boolean(
        string="Radio Contract", compute='_compute_radio_contract', store=True, readonly=False)
    radio_campaign = fields.Char(string="Advertising Campaign")
    radio_brand = fields.Char(string="Brand / Product", help="Brand or product advertised.")
    radio_op_number = fields.Char(
        string="Advertising Order No.",
        help="Number of the advertising order (orden de publicidad) of the advertiser or the "
             "agency. Printed on the invoices and certificates.")
    radio_agency_id = fields.Many2one('res.partner', string="Agency", tracking=True,
                                      domain="[('radio_is_agency', '=', True)]")
    radio_bill_to = fields.Selection(
        selection=[('advertiser', "Advertiser"), ('agency', "Agency")], string="Invoice To",
        default='advertiser')
    radio_commission = fields.Float(string="Agency Commission (%)")
    radio_commission_mode = fields.Selection(
        selection=[('discount', "Discount on the invoice"), ('bill', "Agency commission bill")],
        string="Commission", default='discount',
        help="Discount on the invoice: the commission is deducted on the invoice (it reduces "
             "the base of the ENACOM fee). Agency bill: the advertiser is invoiced in full and "
             "the agency invoices its commission (monthly settlement).")
    radio_is_barter = fields.Boolean(string="Barter", tracking=True,
                                     help="Advertising exchanged for goods or services.")
    radio_barter_invoice = fields.Boolean(
        string="Invoice the Barter", default=True,
        help="Barters are usually invoiced and compensated with the invoice of the counterpart.")
    radio_barter_note = fields.Text(string="Barter Counterpart")
    radio_is_official = fields.Boolean(string="Official Advertising", tracking=True)
    radio_official_body = fields.Char(string="Public Body")
    radio_provider_code = fields.Char(string="Supplier Code",
                                      help="Code of the station as supplier of the public body.")
    radio_suspended = fields.Boolean(string="Suspended", tracking=True, copy=False)
    radio_suspend_reason = fields.Char(string="Suspension Reason", copy=False)
    radio_suspend_debt = fields.Boolean(
        string="Suspended for Debt", copy=False,
        help="Suspended automatically for overdue invoices: it resumes when they are paid.")
    radio_renewal_notified = fields.Boolean(copy=False)
    radio_material_ids = fields.One2many('radio.material', 'subscription_id', string="Materials")
    radio_emission_ids = fields.One2many('radio.emission', 'subscription_id', string="Airings")
    radio_aired_count = fields.Integer(compute='_compute_radio_counts', string="Aired")
    radio_planned_count = fields.Integer(compute='_compute_radio_counts', string="Planned")
    radio_missed_count = fields.Integer(compute='_compute_radio_counts', string="Not Aired")
    radio_material_count = fields.Integer(compute="_compute_radio_counts", string="Material Count")
    radio_material_warning = fields.Boolean(compute='_compute_radio_counts')

    @api.depends('template_id.radio_template')
    def _compute_radio_contract(self):
        for contract in self:
            contract.radio_contract = contract.template_id.radio_template or contract.radio_contract

    def _compute_radio_counts(self):
        data = self.env['radio.emission']._read_group(
            [('subscription_id', 'in', self.ids)], ['subscription_id', 'state'], ['__count'])
        counts = defaultdict(int)
        for contract, state, count in data:
            counts[(contract.id, state)] = count
        today = fields.Date.context_today(self)
        for contract in self:
            contract.radio_aired_count = counts[(contract.id, 'aired')]
            contract.radio_planned_count = counts[(contract.id, 'planned')]
            contract.radio_missed_count = counts[(contract.id, 'missed')] + counts[
                (contract.id, 'conflict')]
            contract.radio_material_count = len(contract.radio_material_ids)
            needs = contract.sale_subscription_line_ids.radio_format_id.filtered(
                'requires_material')
            valid = contract.radio_material_ids.filtered(lambda m: m._is_valid(today))
            contract.radio_material_warning = bool(
                contract.radio_contract and contract.in_progress and needs and not valid)

    @api.onchange('radio_agency_id')
    def _onchange_radio_agency_id(self):
        if self.radio_agency_id:
            self.radio_commission = self.radio_agency_id.radio_agency_commission
        else:
            self.radio_commission = 0.0
            self.radio_bill_to = 'advertiser'

    @api.onchange('partner_id')
    def _onchange_radio_partner(self):
        if self.partner_id.radio_default_agency_id and not self.radio_agency_id:
            self.radio_agency_id = self.partner_id.radio_default_agency_id
            self._onchange_radio_agency_id()
        if self.partner_id.radio_brand and not self.radio_brand:
            self.radio_brand = self.partner_id.radio_brand

    # ------------------------------------------------------------------
    # Daily log planning
    # ------------------------------------------------------------------
    def _radio_plannable(self):
        return self.filtered(lambda c: c.radio_contract and c.active and c.in_progress
                             and not c.radio_suspended)

    @api.model
    def _radio_loads(self, date_from, date_to):
        """Seconds already used per break and per clock hour, and airings per line/day."""
        emissions = self.env['radio.emission'].search([
            ('date', '>=', date_from), ('date', '<=', date_to),
            ('state', 'in', ('planned', 'aired')),
        ])
        break_load, hour_load, line_count, line_break = (defaultdict(int), defaultdict(int),
                                                         defaultdict(int), defaultdict(int))
        for emission in emissions:
            if emission.break_id and emission.format_id.uses_break:
                break_load[(emission.break_id.id, emission.date)] += emission.duration
            if emission.format_id.counts_ad_time:
                hour_load[(emission.company_id.id, emission.date,
                           int(emission.planned_time))] += emission.duration
            line_count[(emission.subscription_line_id.id, emission.date)] += 1
            line_break[(emission.subscription_line_id.id, emission.date,
                        emission.break_id.id)] += 1
        return break_load, hour_load, line_count, line_break

    @staticmethod
    def _radio_pick_material(materials, day, fmt, rotation):
        valid = materials.filtered(lambda m: m._is_valid(day)
                                   and (not m.format_id or m.format_id == fmt))
        if not valid:
            return materials.browse()
        valid = valid.sorted(lambda m: (m.sequence, m.id))
        return valid[rotation % len(valid)]

    def _radio_plan(self, date_from, date_to):
        """Plan the daily log of the contracts between two dates (missing airings only)."""
        contracts = self._radio_plannable()
        if not contracts:
            return self.env['radio.emission']
        Emission = self.env['radio.emission']
        # airings without room are recomputed each time
        Emission.search([('subscription_id', 'in', contracts.ids), ('state', '=', 'conflict'),
                         ('date', '>=', date_from), ('date', '<=', date_to),
                         ('compensation_ids', '=', False)]).unlink()
        break_load, hour_load, line_count, line_break = self._radio_loads(date_from, date_to)
        programs = self.env['radio.program'].search([])
        rotation = defaultdict(int)
        values = []
        for day in self.env['radio.break']._days(date_from, date_to):
            for contract in contracts:
                limit = (contract.company_id.radio_max_ad_minutes or 14.0) * 60
                for line in contract.sale_subscription_line_ids.filtered(
                        lambda l: l.radio_line and l.radio_format_id.kind != 'digital'):
                    if not line._radio_airs_on(day):
                        continue
                    missing = line.radio_spots_per_day - line_count[(line.id, day)]
                    if missing <= 0:
                        continue
                    breaks = line._radio_candidate_breaks(day, programs)
                    done = line_count[(line.id, day)]
                    for _i in range(missing):
                        # spread the spots of the day evenly between the candidate breaks
                        target = (done + _i + 0.5) * len(breaks) / max(line.radio_spots_per_day, 1)
                        chosen = self._radio_choose_break(
                            line, day, breaks, break_load, hour_load, line_break, limit,
                            target=target)
                        values.append(self._radio_emission_values(
                            line, day, chosen, rotation, contract.radio_material_ids))
                        line_count[(line.id, day)] += 1
                        if chosen:
                            self._radio_add_load(line, day, chosen, break_load, hour_load,
                                                 line_break)
        return Emission.create(values)

    @api.model
    def _radio_choose_break(self, line, day, breaks, break_load, hour_load, line_break, limit,
                            after=-1, target=None):
        fmt, duration = line.radio_format_id, line.radio_duration
        company_id = line.sale_subscription_id.company_id.id
        position = {brk.id: index for index, brk in enumerate(breaks)}
        candidates = breaks.filtered(lambda b: b.time > after)
        ordered = sorted(candidates, key=lambda b: (
            line_break[(line.id, day, b.id)],
            abs(position[b.id] + 0.5 - target) if target is not None else 0,
            break_load[(b.id, day)], b.time))
        for brk in ordered:
            if fmt.uses_break and break_load[(brk.id, day)] + duration > brk.capacity:
                continue
            if fmt.counts_ad_time and hour_load[(company_id, day, int(brk.time))] + duration > limit:
                continue
            return brk
        return breaks.browse()

    @api.model
    def _radio_add_load(self, line, day, brk, break_load, hour_load, line_break):
        if line.radio_format_id.uses_break:
            break_load[(brk.id, day)] += line.radio_duration
        if line.radio_format_id.counts_ad_time:
            hour_load[(line.sale_subscription_id.company_id.id, day, int(brk.time))] += \
                line.radio_duration
        line_break[(line.id, day, brk.id)] += 1

    @api.model
    def _radio_emission_values(self, line, day, brk, rotation, materials):
        fmt = line.radio_format_id
        material = self._radio_pick_material(materials, day, fmt, rotation[line.id])
        rotation[line.id] += 1
        sequence = {'first': 1, 'last': 99}.get(line.radio_position, 10)
        return {
            'date': day,
            'break_id': brk.id or False,
            'program_id': (brk.program_id or line.radio_program_id).id or False,
            'planned_time': brk.time if brk else 0.0,
            'sequence': sequence,
            'subscription_id': line.sale_subscription_id.id,
            'subscription_line_id': line.id,
            'format_id': fmt.id,
            'material_id': material.id or False,
            'duration': line.radio_duration,
            'state': 'planned' if brk else 'conflict',
        }

    def _radio_plan_extra(self, line, day, after, source):
        """One extra airing of `line` on `day` after the hour `after` (compensation)."""
        self.ensure_one()
        if not line._radio_airs_on(day) and day != source.date:
            return self.env['radio.emission']
        break_load, hour_load, __, line_break = self._radio_loads(day, day)
        breaks = line._radio_candidate_breaks(day, self.env['radio.program'].search([]))
        limit = (self.company_id.radio_max_ad_minutes or 14.0) * 60
        brk = self._radio_choose_break(line, day, breaks, break_load, hour_load, line_break,
                                       limit, after=after)
        if not brk:
            return self.env['radio.emission']
        values = self._radio_emission_values(line, day, brk, defaultdict(int),
                                             self.radio_material_ids)
        values.update({'compensation_of_id': source.id,
                       'material_id': source.material_id.id or values['material_id']})
        return self.env['radio.emission'].create(values)

    def action_radio_plan(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_radio.radio_schedule_generate_action')
        action['context'] = {'default_subscription_ids': self.ids}
        return action

    def action_radio_view_emissions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_radio.radio_emission_action')
        action['domain'] = [('subscription_id', '=', self.id)]
        action['context'] = {'default_subscription_id': self.id}
        return action

    def action_radio_view_materials(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_radio.radio_material_action')
        action['domain'] = [('subscription_id', '=', self.id)]
        action['context'] = {'default_subscription_id': self.id}
        return action

    def action_radio_certificate(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_radio.radio_certificate_wizard_action')
        action['context'] = {'default_subscription_id': self.id}
        return action

    @api.model
    def _cron_radio_plan(self):
        today = fields.Date.context_today(self)
        # contracts with an end date (campaigns) are closed the day after it
        for contract in self.search([('radio_contract', '=', True), ('in_progress', '=', True),
                                     ('date', '!=', False), ('date', '<', today)]):
            contract.close_subscription()
        for company in self.env['res.company'].sudo().search([]):
            days = company.radio_schedule_days or 7
            contracts = self.sudo().with_company(company).search([
                ('company_id', '=', company.id), ('radio_contract', '=', True),
                ('in_progress', '=', True)])
            contracts._radio_plan(today, today + timedelta(days=days))

    # ------------------------------------------------------------------
    # Suspension (overdue invoices) - own flag: the stages of subscription_oca reset the
    # start date when a contract goes back to "in progress"
    # ------------------------------------------------------------------
    def action_radio_suspend(self, reason=None, debt=False):
        today = fields.Date.context_today(self)
        for contract in self.filtered(lambda c: not c.radio_suspended):
            future = contract.radio_emission_ids.filtered(
                lambda e: e.state in ('planned', 'conflict') and e.date >= today)
            future.write({'state': 'cancelled', 'note': self.env._("Contract suspended")})
            contract.write({'radio_suspended': True, 'radio_suspend_debt': debt,
                            'radio_suspend_reason': reason or self.env._("Suspended manually")})
            contract.message_post(body=self.env._(
                "Airing suspended: %(reason)s. %(count)s planned spots cancelled.",
                reason=contract.radio_suspend_reason, count=len(future)))
        return True

    def action_radio_resume(self):
        today = fields.Date.context_today(self)
        for contract in self.filtered('radio_suspended'):
            contract.write({'radio_suspended': False, 'radio_suspend_reason': False,
                            'radio_suspend_debt': False})
            contract.message_post(body=self.env._("Airing resumed."))
            days = contract.company_id.radio_schedule_days or 7
            contract._radio_plan(today, today + timedelta(days=days))
        return True

    def _radio_overdue_invoices(self, days):
        self.ensure_one()
        limit = fields.Date.context_today(self) - timedelta(days=days)
        partner = (self.radio_agency_id if self.radio_bill_to == 'agency' and self.radio_agency_id
                   else self.partner_id).commercial_partner_id
        return self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
            ('commercial_partner_id', '=', partner.id),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('invoice_date_due', '<', limit),
        ])

    @api.model
    def _cron_radio_credit_control(self):
        for company in self.env['res.company'].sudo().search([('radio_suspend_days', '>', 0)]):
            contracts = self.sudo().with_company(company).search([
                ('company_id', '=', company.id), ('radio_contract', '=', True),
                ('in_progress', '=', True)])
            for contract in contracts:
                overdue = contract._radio_overdue_invoices(company.radio_suspend_days)
                if overdue and not contract.radio_suspended:
                    contract.action_radio_suspend(self.env._(
                        "Overdue invoices: %s", ", ".join(overdue.mapped('name'))), debt=True)
                elif not overdue and contract.radio_suspended and contract.radio_suspend_debt:
                    contract.action_radio_resume()

    @api.model
    def _cron_radio_renewals(self):
        """Renewal activity 30 days before the end of the contracts."""
        limit = fields.Date.context_today(self) + timedelta(days=30)
        contracts = self.search([('radio_contract', '=', True), ('in_progress', '=', True),
                                 ('date', '!=', False), ('date', '<=', limit),
                                 ('radio_renewal_notified', '=', False)])
        for contract in contracts:
            contract.write({'to_renew': True, 'radio_renewal_notified': True})
            contract.activity_schedule(
                'mail.mail_activity_data_todo', date_deadline=contract.date,
                summary=self.env._("Renew the advertising contract"),
                user_id=contract.user_id.id or self.env.user.id)

    # ------------------------------------------------------------------
    # Invoicing
    # ------------------------------------------------------------------
    def _radio_step(self):
        self.ensure_one()
        template = self.template_id
        return relativedelta(**{template.recurring_rule_type or 'months':
                                int(template.recurring_interval or 1)})

    def _radio_period(self):
        """(start, end) of the period invoiced now."""
        self.ensure_one()
        template = self.template_id
        step = self._radio_step()
        date_ref = self.recurring_next_date or fields.Date.context_today(self)
        if template.radio_billing_basis == 'aired':
            return date_ref - step, date_ref - timedelta(days=1)
        return date_ref, date_ref + step - timedelta(days=1)

    def _radio_invoice_partner(self):
        self.ensure_one()
        if self.radio_bill_to == 'agency' and self.radio_agency_id:
            return self.radio_agency_id
        return self.partner_id

    def _prepare_account_move(self, line_ids):
        values = super()._prepare_account_move(line_ids)
        if not self.radio_contract:
            return values
        partner = self._radio_invoice_partner()
        start, end = self._radio_period()
        fiscal_position = self.env['account.fiscal.position'].with_company(
            self.company_id)._get_fiscal_position(partner)
        refs = [ref for ref in (self.radio_op_number, self.radio_campaign) if ref]
        values.update({
            'partner_id': partner.id,
            'invoice_payment_term_id': partner.property_payment_term_id.id,
            'invoice_date_due': (values.get('invoice_date')
                                 if not partner.property_payment_term_id else False),
            'fiscal_position_id': fiscal_position.id,
            'ref': " / ".join(refs) or False,
            'radio_period_start': start,
            'radio_period_end': end,
            'l10n_ar_afip_service_start': start,
            'l10n_ar_afip_service_end': end,
        })
        if self.radio_is_official:
            values['narration'] = Markup("<p>%s</p>") % self.env._(
                "Official advertising - %(body)s - Advertising order %(op)s - Campaign "
                "%(campaign)s - Supplier code %(code)s",
                body=self.radio_official_body or '-', op=self.radio_op_number or '-',
                campaign=self.radio_campaign or '-', code=self.radio_provider_code or '-')
        return values

    def _radio_aired_to_invoice(self, line, start, end):
        return self.radio_emission_ids.filtered(
            lambda e: e.subscription_line_id == line and e.state == 'aired'
            and not e.invoice_id and start <= e.date <= end)

    def _radio_commission_lines(self, line_values):
        """Agency commission as discount lines on the invoice (one per set of taxes)."""
        self.ensure_one()
        product = self.company_id.radio_agency_commission_product_id
        if not (self.radio_agency_id and self.radio_commission and product
                and (self.radio_commission_mode or 'discount') == 'discount'):
            return []
        by_taxes = defaultdict(float)
        for values in line_values:
            taxes = tuple(sorted(values['tax_ids'][0][2])) if values.get('tax_ids') else ()
            by_taxes[taxes] += values['quantity'] * values['price_unit'] * (
                1 - (values.get('discount') or 0.0) / 100.0)
        account = (product.property_account_income_id
                   or product.categ_id.property_account_income_categ_id)
        lines = []
        for taxes, amount in by_taxes.items():
            lines.append({
                'product_id': product.id,
                'name': self.env._("Agency commission %(rate)s%% - %(agency)s",
                                   rate=self.radio_commission, agency=self.radio_agency_id.name),
                'quantity': 1,
                'price_unit': -self.currency_id.round(amount * self.radio_commission / 100.0),
                'tax_ids': [Command.set(list(taxes))],
                'account_id': account.id or False,
            })
        return lines

    def create_invoice(self):
        if not self.radio_contract:
            return super().create_invoice()
        self.ensure_one()
        start, end = self._radio_period()
        aired_basis = self.template_id.radio_billing_basis == 'aired'
        line_values, billed = [], self.env['radio.emission']
        for line in self.sale_subscription_line_ids:
            values = line._prepare_account_move_line()
            if aired_basis and line.radio_line:
                aired = self._radio_aired_to_invoice(line, start, end)
                if not aired:
                    continue
                values['quantity'] = len(aired)
                billed |= aired
            if not values.get('quantity'):
                continue
            line_values.append(values)
        if not line_values:
            return self.env['account.move']
        line_values += self._radio_commission_lines(line_values)
        for values in line_values:
            if not values.get('account_id'):   # commission product without account
                values.pop('account_id', None)
        invoice_values = self._prepare_account_move([Command.create(v) for v in line_values])
        invoice = (self.env['account.move'].sudo()
                   .with_context(default_move_type='out_invoice', journal_type='sale')
                   .create(invoice_values))
        billed.write({'invoice_id': invoice.id})
        if self.template_id.radio_attach_certificate and aired_basis:
            self._radio_attach_certificate(invoice, start, end)
        return invoice

    def _radio_attach_certificate(self, invoice, start, end):
        """Attach the broadcast certificate of the period to the invoice."""
        self.ensure_one()
        try:
            pdf, __ = self.env['ir.actions.report'].with_context(
                radio_date_from=start, radio_date_to=end)._render_qweb_pdf(
                'odossey_radio.action_report_radio_certificate', self.ids)
        except Exception:  # noqa: BLE001 - never block the invoicing for the attachment
            _logger.exception("Radio: broadcast certificate of %s not generated", self.name)
            return
        name = self.env._("Broadcast certificate %(contract)s %(start)s-%(end)s",
                          contract=self.name, start=start, end=end)
        attachment = self.env['ir.attachment'].sudo().create({
            'name': f"{name}.pdf", 'type': 'binary', 'datas': base64.b64encode(pdf),
            'res_model': 'account.move', 'res_id': invoice.id, 'mimetype': 'application/pdf',
        })
        invoice.sudo().message_post(body=self.env._("Broadcast certificate of the period."),
                                    attachment_ids=attachment.ids)

    def generate_invoice(self):
        if not self.radio_contract:
            return super().generate_invoice()
        if self.radio_suspended or (self.radio_is_barter and not self.radio_barter_invoice):
            reason = (self.env._("contract suspended") if self.radio_suspended
                      else self.env._("barter not invoiced"))
            self.recurring_next_date = self.recurring_next_date + self._radio_step()
            self.message_post(body=self.env._("Period not invoiced: %s.", reason))
            return self.env['account.move']
        start, end = self._radio_period()
        if self.template_id.radio_billing_basis == 'aired' and not any(
                self._radio_aired_to_invoice(line, start, end)
                for line in self.sale_subscription_line_ids.filtered('radio_line')):
            self.recurring_next_date = self.recurring_next_date + self._radio_step()
            self.message_post(body=self.env._(
                "No spots aired between %(start)s and %(end)s: nothing to invoice.",
                start=start, end=end))
            return self.env['account.move']
        return super().generate_invoice()

    def manual_invoice(self):
        if self.radio_contract:
            invoice = self.create_invoice()
            if not invoice:
                raise UserError(self.env._("There is nothing to invoice for the current period."))
            self.calculate_recurring_next_date(self.recurring_next_date)
            return {
                'type': 'ir.actions.act_window', 'res_model': 'account.move',
                'res_id': invoice.id, 'view_mode': 'form', 'name': self.name,
            }
        return super().manual_invoice()

    def _radio_certificate_emissions(self, date_from, date_to):
        self.ensure_one()
        return self.radio_emission_ids.filtered(
            lambda e: e.state == 'aired' and date_from <= e.date <= date_to
        ).sorted(lambda e: (e.date, e.planned_time, e.sequence))

    # ------------------------------------------------------------------
    # Lines coming from the advertising order
    # ------------------------------------------------------------------
    @api.model
    def _radio_line_values(self, order_line):
        values = {name: order_line[name].id if hasattr(order_line[name], 'id')
                  else order_line[name] for name in RADIO_LINE_FIELDS}
        values['radio_weekday_ids'] = [Command.set(order_line.radio_weekday_ids.ids)]
        return values
