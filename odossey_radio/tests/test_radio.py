from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import HttpCase, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestRadio(AccountTestInvoicingCommon, HttpCase):

    @classmethod
    @AccountTestInvoicingCommon.setup_chart_template('ar_ri')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.env.user.group_ids |= cls.env.ref('odossey_radio.group_radio_manager')
        cls.company.partner_id.write({
            'l10n_ar_afip_responsibility_type_id': cls.env.ref('l10n_ar.res_IVARI').id,
            'l10n_latam_identification_type_id': cls.env.ref('l10n_ar.it_cuit').id,
            'vat': '30111111118',
        })
        cls.company.write({'l10n_ar_afip_start_date': date(2020, 1, 1),
                           'radio_max_ad_minutes': 14.0})
        cls.env['res.company']._subscription_ensure_pricelists()
        cls.today = fields.Date.context_today(cls.env.user)
        ref = cls.env.ref
        cls.weekdays = cls.env['radio.weekday'].search([('code', '<', 5)])
        cls.everyday = cls.env['radio.weekday'].search([])
        cls.spot = ref('odossey_radio.format_spot')
        cls.mention = ref('odossey_radio.format_mention')
        cls.tpl_fixed = ref('odossey_radio.template_monthly_fixed')
        cls.tpl_aired = ref('odossey_radio.template_monthly_aired')
        cls.program = cls.env['radio.program'].create({
            'name': "Morning show", 'weekday_ids': [Command.set(cls.everyday.ids)],
            'hour_from': 8.0, 'hour_to': 10.0,
        })
        cls.program.break_ids = [Command.create({'time': 8.5, 'capacity': 60}),
                                 Command.create({'time': 9.5, 'capacity': 60})]
        tax = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id), ('type_tax_use', '=', 'sale'),
            ('tax_group_id.l10n_ar_vat_afip_code', '=', '5')], limit=1)
        cls.tax = tax
        cls.product = cls._radio_product("Spot 30s", cls.spot, 30, cls.tpl_fixed)
        cls.product_aired = cls._radio_product("Spot 30s aired", cls.spot, 30, cls.tpl_aired)
        cls.advertiser = cls.env['res.partner'].create({
            'name': "Advertiser SA", 'vat': '30714295698', 'radio_is_advertiser': True,
            'l10n_latam_identification_type_id': ref('l10n_ar.it_cuit').id,
            'l10n_ar_afip_responsibility_type_id': ref('l10n_ar.res_IVARI').id,
            'email': 'advertiser@example.com',
        })
        cls.agency = cls.env['res.partner'].create({
            'name': "Agency SA", 'vat': '30712345674', 'radio_is_agency': True,
            'radio_agency_commission': 15.0,
            'l10n_latam_identification_type_id': ref('l10n_ar.it_cuit').id,
            'l10n_ar_afip_responsibility_type_id': ref('l10n_ar.res_IVARI').id,
        })

    @classmethod
    def _radio_product(cls, name, fmt, duration, template):
        return cls.env['product.product'].create({
            'name': name, 'type': 'service', 'radio_ok': True, 'invoice_policy': 'delivery',
            'radio_format_id': fmt.id, 'radio_duration': duration, 'list_price': 1000.0,
            'subscribable': True, 'subscription_template_id': template.id,
            'taxes_id': [Command.set(cls.tax.ids)],
            'property_account_income_id': cls.company_data['default_account_revenue'].id,
        })

    def _order(self, product=None, per_day=2, start=None, **vals):
        order = self.env['sale.order'].create(dict({
            'partner_id': self.advertiser.id,
            'radio_date_start': start or self.today,
            'order_line': [Command.create({
                'product_id': (product or self.product).id,
                'radio_program_id': self.program.id,
                'radio_weekday_ids': [Command.set(self.everyday.ids)],
                'radio_spots_per_day': per_day, 'product_uom_qty': 10,
            })],
        }, **vals))
        order.action_confirm()
        return order, order.subscription_ids

    # ------------------------------------------------------------------
    def test_01_order_becomes_contract(self):
        order, contract = self._order(radio_agency_id=self.agency.id, radio_bill_to='agency',
                                      radio_commission=15.0, radio_campaign="Summer",
                                      radio_date_end=self.today + timedelta(days=60))
        self.assertTrue(order.radio_order)
        self.assertEqual(len(contract), 1)
        self.assertTrue(contract.radio_contract and contract.in_progress)
        self.assertEqual(contract.radio_agency_id, self.agency)
        self.assertEqual(contract.radio_campaign, "Summer")
        self.assertEqual(contract.date_start, self.today)
        self.assertEqual(contract.date, self.today + timedelta(days=60))
        line = contract.sale_subscription_line_ids
        self.assertEqual((line.radio_format_id, line.radio_program_id, line.radio_spots_per_day),
                         (self.spot, self.program, 2))
        # the log of the next days is planned at confirmation
        self.assertTrue(contract.radio_emission_ids)

    def test_02_plan_respects_capacity(self):
        """Two breaks of 60 s: at most 2 spots of 30 s each -> 4 per day, the rest no room."""
        __, contract = self._order(per_day=6)
        day = self.today + timedelta(days=1)
        emissions = contract.radio_emission_ids.filtered(lambda e: e.date == day)
        self.assertEqual(len(emissions), 6)
        self.assertEqual(len(emissions.filtered(lambda e: e.state == 'planned')), 4)
        self.assertEqual(len(emissions.filtered(lambda e: e.state == 'conflict')), 2)
        for brk in self.program.break_ids:
            used = sum(emissions.filtered(lambda e, b=brk: e.break_id == b).mapped('duration'))
            self.assertLessEqual(used, brk.capacity)
        # planning again does not duplicate
        contract._radio_plan(day, day)
        self.assertEqual(len(contract.radio_emission_ids.filtered(
            lambda e: e.date == day and e.state == 'planned')), 4)

    def test_03_hourly_legal_limit(self):
        self.program.break_ids.write({'capacity': 3600})
        self.company.radio_max_ad_minutes = 1.0      # 60 s per clock hour
        __, contract = self._order(per_day=6)
        day = self.today + timedelta(days=1)
        planned = contract.radio_emission_ids.filtered(lambda e: e.date == day
                                                       and e.state == 'planned')
        by_hour = {}
        for emission in planned:
            by_hour[int(emission.planned_time)] = by_hour.get(int(emission.planned_time), 0) + \
                emission.duration
        self.assertTrue(all(seconds <= 60 for seconds in by_hour.values()), by_hour)
        self.assertEqual(len(planned), 4)

    def test_04_weekdays_and_mentions(self):
        product = self._radio_product("Mention 20s", self.mention, 20, self.tpl_fixed)
        order = self.env['sale.order'].create({
            'partner_id': self.advertiser.id, 'radio_date_start': self.today,
            'order_line': [Command.create({
                'product_id': product.id, 'radio_program_id': self.program.id,
                'radio_weekday_ids': [Command.set(self.weekdays.ids)], 'radio_spots_per_day': 5})],
        })
        order.action_confirm()
        contract = order.subscription_ids
        contract._radio_plan(self.today, self.today + timedelta(days=13))
        emissions = contract.radio_emission_ids
        self.assertTrue(emissions)
        self.assertFalse(emissions.filtered(lambda e: e.date.weekday() >= 5), "Weekdays only")
        # live mentions do not use the capacity of the breaks
        self.assertFalse(emissions.filtered(lambda e: e.state == 'conflict'))

    def test_05_materials_rotation_and_approval(self):
        __, contract = self._order(per_day=2)
        Material = self.env['radio.material']
        restricted = Material.create({'name': "Beer spot", 'subscription_id': contract.id,
                                      'kind': 'audio', 'audio_file': b'UklGRg==',
                                      'restriction': 'alcohol'})
        with self.assertRaises(UserError):
            restricted.action_approve()
        restricted.authorization_ref = "OK 123"
        restricted.action_approve()
        # approving assigns the material to the planned spots without one
        planned = contract.radio_emission_ids.filtered(lambda e: e.state == 'planned')
        self.assertEqual(set(planned.material_id.ids), {restricted.id})
        second = Material.create({'name': "Spot v2", 'subscription_id': contract.id,
                                  'kind': 'audio', 'audio_file': b'UklGRg==', 'state': 'approved',
                                  'sequence': 2})
        day = self.today + timedelta(days=10)
        emissions = contract._radio_plan(day, day)
        self.assertEqual(set(emissions.material_id.ids), {restricted.id, second.id}, "Rotation")

    def test_06_invoice_fixed_fee_with_agency_discount(self):
        __, contract = self._order(radio_agency_id=self.agency.id, radio_bill_to='agency',
                                   radio_commission=15.0, radio_commission_mode='discount',
                                   radio_op_number="OP-1")
        invoice = contract.generate_invoice()
        self.assertEqual(invoice.partner_id, self.agency, "Billed to the agency")
        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.l10n_ar_afip_service_start, self.today)
        self.assertEqual(invoice.l10n_ar_afip_service_end,
                         self.today + relativedelta(months=1) - timedelta(days=1))
        self.assertIn("OP-1", invoice.ref)
        commission = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.company.radio_agency_commission_product_id)
        self.assertAlmostEqual(commission.price_subtotal, -10 * 1000.0 * 0.15)
        self.assertAlmostEqual(invoice.amount_untaxed, 10 * 1000.0 * 0.85)
        self.assertEqual(contract.recurring_next_date, self.today + relativedelta(months=1))

    def test_07_invoice_aired_spots(self):
        start = self.today.replace(day=1) - relativedelta(months=1)
        __, contract = self._order(product=self.product_aired, per_day=1, start=start)
        contract._radio_plan(start, self.today)
        month = contract.radio_emission_ids.filtered(
            lambda e: e.date < start + relativedelta(months=1))
        month.write({'state': 'aired'})
        month[:2].write({'state': 'missed'})
        self.assertEqual(contract.recurring_next_date, start + relativedelta(months=1))
        invoice = contract.generate_invoice()
        line = invoice.invoice_line_ids.filtered(lambda l: l.product_id == self.product_aired)
        self.assertEqual(line.quantity, len(month) - 2, "Only aired spots are invoiced")
        self.assertEqual(invoice.l10n_ar_afip_service_start, start)
        self.assertEqual(set(invoice.radio_emission_ids.ids), set((month - month[:2]).ids))
        self.assertTrue(self.env['ir.attachment'].search_count(
            [('res_model', '=', 'account.move'), ('res_id', '=', invoice.id)]),
            "Broadcast certificate attached")
        # nothing aired in the next period yet -> no invoice, next date advanced anyway
        next_date = contract.recurring_next_date
        self.assertFalse(contract.generate_invoice())
        self.assertEqual(contract.recurring_next_date, next_date + relativedelta(months=1))

    def test_08_suspension_and_barter(self):
        __, contract = self._order(per_day=2)
        future = contract.radio_emission_ids.filtered(lambda e: e.state == 'planned')
        contract.action_radio_suspend("test")
        self.assertTrue(contract.radio_suspended)
        self.assertEqual(set(future.mapped('state')), {'cancelled'})
        self.assertFalse(contract._radio_plan(self.today, self.today + timedelta(days=3)))
        next_date = contract.recurring_next_date
        self.assertFalse(contract.generate_invoice(), "Suspended: not invoiced")
        self.assertEqual(contract.recurring_next_date, next_date + relativedelta(months=1))
        contract.action_radio_resume()
        self.assertFalse(contract.radio_suspended)
        self.assertTrue(contract.radio_emission_ids.filtered(lambda e: e.state == 'planned'))
        __, barter = self._order(radio_is_barter=True)
        barter.radio_barter_invoice = False
        self.assertFalse(barter.generate_invoice())

    def test_09_credit_control(self):
        self.company.radio_suspend_days = 10
        __, contract = self._order(per_day=1)
        invoice = contract.generate_invoice()
        invoice.invoice_date_due = self.today - timedelta(days=20)
        self.env['sale.subscription']._cron_radio_credit_control()
        self.assertTrue(contract.radio_suspended)
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({})._create_payments()
        self.env['sale.subscription']._cron_radio_credit_control()
        self.assertFalse(contract.radio_suspended, "Resumed once paid")

    def test_10_compensation_and_confirmation(self):
        __, contract = self._order(per_day=1)
        emission = contract.radio_emission_ids.filtered(lambda e: e.state == 'planned')[:1]
        emission.action_mark_missed()
        self.assertEqual(emission.state, 'missed')
        emission.action_compensate()
        self.assertTrue(emission.compensation_ids)
        past = contract.radio_emission_ids.filtered(lambda e: e.state == 'planned')[:1]
        past.date = self.today - timedelta(days=1)
        self.env['radio.emission']._cron_confirm_past()
        self.assertEqual(past.state, 'aired')

    def test_11_reports_and_certificate(self):
        start = self.today.replace(day=1) - relativedelta(months=1)
        __, contract = self._order(per_day=1, start=start)
        contract._radio_plan(start, self.today)
        contract.radio_emission_ids.filtered(lambda e: e.date < self.today).write({'state': 'aired'})
        wizard = self.env['radio.certificate.wizard'].create({
            'subscription_id': contract.id, 'date_from': start,
            'date_to': start + relativedelta(months=1, days=-1)})
        self.assertTrue(wizard.aired_count)
        Report = self.env['ir.actions.report'].with_context(force_report_rendering=True)
        pdf, __ = Report._render_qweb_pdf(
            'odossey_radio.action_report_radio_certificate', contract.ids,
            data={'radio_date_from': str(start), 'radio_date_to': str(self.today)})
        self.assertTrue(pdf.startswith(b'%PDF'))
        for report in ('action_report_radio_log', 'action_report_radio_grid',
                       'action_report_radio_order'):
            model = self.env.ref(f'odossey_radio.{report}').model
            ids = (contract.radio_emission_ids[:5].ids if model == 'radio.emission'
                   else self.program.ids if model == 'radio.program' else contract.sale_order_id.ids)
            pdf, __ = Report._render_qweb_pdf(f'odossey_radio.{report}', ids)
            self.assertTrue(pdf.startswith(b'%PDF'), report)
        contract.generate_invoice()
        self.env.flush_all()
        self.assertTrue(self.env['radio.revenue.report'].search_count(
            [('subscription_id', '=', contract.id)]))
        self.assertTrue(self.env['radio.occupancy.report'].search_count(
            [('program_id', '=', self.program.id), ('used', '>', 0)]))

    def test_12_enacom_rate_and_pricelists(self):
        self.company.write({'radio_enacom_category': 'a', 'radio_band': 'fm'})
        self.assertEqual(self.company.radio_enacom_rate, 2.5)
        self.company.write({'radio_enacom_category': 'd', 'radio_band': 'am'})
        self.assertEqual(self.company.radio_enacom_rate, 0.5)
        self.assertTrue(self.env.user.has_group('product.group_product_pricelist'))

    def test_13_generate_breaks(self):
        program = self.env['radio.program'].create({
            'name': "Afternoon", 'weekday_ids': [Command.set(self.weekdays.ids)],
            'hour_from': 14.0, 'hour_to': 16.0})
        self.company.write({'radio_break_interval': 30, 'radio_break_offset': 25})
        program.action_generate_breaks()
        self.assertEqual(len(program.break_ids), 4)
        self.assertAlmostEqual(program.break_ids[0].time, 14 + 25 / 60)

    def test_14_portal(self):
        start = self.today.replace(day=1) - relativedelta(months=1)
        __, contract = self._order(per_day=1, start=start)
        contract._radio_plan(start, self.today)
        contract.radio_emission_ids.filtered(lambda e: e.date < self.today).write({'state': 'aired'})
        user = self.env['res.users'].create({
            'name': "Portal advertiser", 'login': 'radio_portal', 'password': 'radio_portal_1',
            'partner_id': self.advertiser.id,
            'group_ids': [Command.set(self.env.ref('base.group_portal').ids)]})
        self.authenticate(user.login, 'radio_portal_1')
        response = self.url_open('/my/radio')
        self.assertEqual(response.status_code, 200)
        self.assertIn(contract.name, response.text)
        response = self.url_open(f'/my/radio/{contract.id}')
        self.assertEqual(response.status_code, 200)
        response = self.url_open(f'/my/radio/{contract.id}/certificate/{start}')
        self.assertEqual(response.headers['Content-Type'], 'application/pdf')
        other = self.env['res.partner'].create({'name': "Other"})
        __, other_contract = self._order(partner_id=other.id)
        self.assertEqual(self.url_open(f'/my/radio/{other_contract.id}').status_code, 404)

    def test_15_demo_loader(self):
        Program = self.env['radio.program'].with_company(self.company)
        Program._radio_load_demo_data()
        contracts = self.env['sale.subscription'].search([('radio_contract', '=', True),
                                                          ('company_id', '=', self.company.id)])
        self.assertGreaterEqual(len(contracts), 9)
        self.assertTrue(contracts.filtered('radio_is_barter'))
        self.assertTrue(contracts.filtered('radio_is_official'))
        self.assertTrue(contracts.filtered('radio_suspended'), "An overdue advertiser is suspended")
        self.assertTrue(contracts.filtered(lambda c: c.radio_agency_id and c.radio_bill_to == 'agency'))
        self.assertEqual({'fixed', 'aired'}, set(contracts.template_id.mapped('radio_billing_basis')))
        emissions = contracts.radio_emission_ids
        self.assertTrue({'aired', 'planned', 'missed'} <= set(emissions.mapped('state')))
        self.assertTrue(contracts.invoice_ids)
        self.assertTrue(self.env['account.move'].search_count([
            ('move_type', '=', 'in_invoice'), ('partner_id.radio_is_agency', '=', True)]),
            "Agency commission bill")
        with self.assertRaises(UserError):
            Program._radio_load_demo_data()
