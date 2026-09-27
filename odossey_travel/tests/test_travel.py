from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestTravel(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_chart_template('ar_ri')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.env.user.group_ids |= cls.env.ref('odossey_travel.group_travel_manager')
        cls.company.partner_id.write({
            'l10n_ar_afip_responsibility_type_id': cls.env.ref('l10n_ar.res_IVARI').id,
            'l10n_latam_identification_type_id': cls.env.ref('l10n_ar.it_cuit').id,
            'vat': '30111111118',
        })
        cls.company.write({
            'l10n_ar_afip_start_date': date(2020, 1, 1),
            'travel_cancel_rate_pending': 20.0,
            'travel_cancel_rate_deposit': 10.0,
            'travel_cancel_rate_paid': 0.0,
            'travel_quotation_win_rate': 50.0,
            'travel_iibb_rate': 5.0,
            'travel_iibb_base': 'revenue',
            'travel_payment_fee_rate': 0.0,
        })
        Tax = cls.env['account.tax']

        def tax(code):
            return Tax.search([('company_id', '=', cls.company.id), ('type_tax_use', '=', 'sale'),
                               ('tax_group_id.l10n_ar_vat_afip_code', '=', code)], limit=1)

        cls.tax_exempt = tax('2')
        cls.tax_21 = tax('5')
        Product = cls.env['product.product']
        cls.flight = Product.create({
            'name': "Flight", 'type': 'service', 'invoice_policy': 'order',
            'travel_service_type': 'flight', 'taxes_id': [Command.set(cls.tax_exempt.ids)]})
        cls.agency = Product.create({
            'name': "Agency services", 'type': 'service', 'invoice_policy': 'order',
            'travel_service_type': 'commission', 'taxes_id': [Command.set(cls.tax_21.ids)]})
        cls.policy = cls.env['travel.cancellation.policy'].create({
            'name': "Test policy",
            'deposit_refundable': False,
            'rule_ids': [Command.create({'days_before': 60, 'penalty_percent': 50}),
                         Command.create({'days_before': 7, 'penalty_percent': 100})],
        })
        cls.today = fields.Date.context_today(cls.env.user)
        cls.trip = cls.env['travel.trip'].create({
            'name': "Test trip",
            'destination': "Salta",
            'country_id': cls.env.ref('base.ar').id,
            'currency_id': cls.company.currency_id.id,
            'date_start': cls.today + timedelta(days=90),
            'date_end': cls.today + timedelta(days=97),
            'capacity': 5,
            'deposit_type': 'fixed',
            'deposit_amount': 300.0,
            'cancellation_policy_id': cls.policy.id,
            'component_ids': [
                Command.create({'product_id': cls.flight.id, 'price_unit': 900.0,
                                'cost_unit': 800.0}),
                Command.create({'product_id': cls.agency.id, 'price_unit': 100.0,
                                'cost_unit': 0.0}),
            ],
        })
        cls.trip.action_open()
        Partner = cls.env['res.partner']
        cf = cls.env.ref('l10n_ar.res_CF').id
        dni = cls.env.ref('l10n_ar.it_dni').id

        def person(name, number):
            return Partner.create({'name': name, 'vat': number,
                                   'l10n_latam_identification_type_id': dni,
                                   'l10n_ar_afip_responsibility_type_id': cf})

        cls.father = person("Father", '20111222')
        cls.mother = person("Mother", '20111333')
        cls.child = person("Child", '45111444')
        cls.friend_a = person("Friend A", '30111555')
        cls.friend_b = person("Friend B", '30111666')

    def _booking(self, partners, confirm=True):
        order = self.env['sale.order'].create({
            'partner_id': partners[0].id,
            'trip_id': self.trip.id,
            'travel_passenger_ids': [Command.create({'partner_id': p.id}) for p in partners],
        })
        order._travel_load_services()
        if confirm:
            order.action_confirm()
        return order

    def _pay(self, invoices, amount=None):
        invoices.filtered(lambda m: m.state == 'draft').action_post()
        for invoice in invoices:
            self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=invoice.ids,
            ).create({'amount': amount or invoice.amount_residual})._create_payments()

    def _invoice_deposit(self, order, amount=None):
        wizard = self.env['sale.advance.payment.inv'].with_context(
            active_model='sale.order', active_ids=order.ids).create({
                'advance_payment_method': 'fixed',
                'fixed_amount': amount or order.travel_deposit_required,
            })
        return wizard._create_invoices(order)

    # ------------------------------------------------------------------
    def test_01_services_and_prices(self):
        order = self._booking(self.father | self.mother, confirm=False)
        lines = order.order_line.filtered('travel_component_id')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines.mapped('product_uom_qty'), [2.0, 2.0])
        self.assertEqual(sorted(lines.mapped('price_unit')), [100.0, 900.0])
        self.assertEqual(order.amount_untaxed, 2000.0)
        self.assertEqual(order.travel_deposit_required, 600.0)
        self.assertEqual(order.travel_booking_state, 'quotation')
        # a new trip price is applied to open quotations only
        self.trip.component_ids.filtered(lambda c: c.product_id == self.flight).price_unit = 1000
        self.trip.action_update_quotation_prices()
        self.assertEqual(order.amount_untaxed, 2200.0)
        lines = order.order_line.filtered('travel_component_id')
        # changing the quantity keeps the trip price (not the product list price)
        lines.filtered(lambda l: l.product_id == self.flight).product_uom_qty = 3
        self.assertEqual(
            lines.filtered(lambda l: l.product_id == self.flight).price_unit, 1000.0)

    def test_02_deposit_freezes_price(self):
        order = self._booking(self.father | self.mother)
        self.assertEqual(order.travel_booking_state, 'pending')
        self.assertFalse(order.travel_price_frozen)
        deposit = self._invoice_deposit(order)
        deposit.action_post()
        self.assertFalse(order.travel_price_frozen, "Posted but unpaid deposit")
        self._pay(deposit)
        self.assertTrue(order.travel_price_frozen)
        self.assertEqual(order.travel_booking_state, 'deposit')
        self.assertEqual(order.travel_frozen_date, self.today)
        self.assertAlmostEqual(order.travel_amount_paid, 600.0)
        # frozen: the services of a confirmed booking cannot be reloaded at the new price
        self.trip.component_ids[0].price_unit = 5000
        with self.assertRaises(UserError):
            order._travel_load_services()
        final = order._create_invoices(final=True)
        self._pay(final)
        self.assertEqual(order.travel_booking_state, 'paid')
        self.assertAlmostEqual(order.travel_amount_due, 0.0)
        # ARCA service dates = trip dates
        self.assertEqual(final.l10n_ar_afip_service_start, self.trip.date_start)
        self.assertEqual(final.trip_id, self.trip)

    def test_03_capacity(self):
        self._booking(self.father | self.mother | self.child)
        order = self._booking(self.friend_a | self.friend_b | self.env['res.partner'].create(
            {'name': "Extra"}), confirm=False)
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(self.trip.seats_reserved, 3)
        self.assertEqual(self.trip.seats_quoted, 3)

    def test_04_cancellation_penalty(self):
        order = self._booking(self.father)
        self._pay(self._invoice_deposit(order))
        wizard = self.env['travel.booking.cancel'].create({
            'sale_order_id': order.id, 'reason': "Test",
            'cancel_date': self.trip.date_start - timedelta(days=30)})
        # 30 days before -> 50%, total 1021 (VAT 21% on 100)
        self.assertEqual(wizard.penalty_percent, 50.0)
        self.assertAlmostEqual(wizard.penalty_amount, 510.5)
        self.assertAlmostEqual(wizard.amount_owed, 210.5)
        wizard.action_confirm()
        self.assertEqual(order.state, 'cancel')
        self.assertEqual(order.travel_booking_state, 'cancelled')
        self.assertAlmostEqual(order.travel_penalty_amount, 510.5)
        # far from the departure: the non refundable deposit is retained anyway
        order2 = self._booking(self.mother)
        self._pay(self._invoice_deposit(order2))
        wizard2 = self.env['travel.booking.cancel'].create({
            'sale_order_id': order2.id, 'reason': "Test",
            'cancel_date': self.trip.date_start - timedelta(days=80)})
        self.assertEqual(wizard2.penalty_percent, 0.0)
        self.assertAlmostEqual(wizard2.penalty_amount, 300.0)
        self.assertAlmostEqual(wizard2.refund_amount, 0.0)

    def test_05_forecast(self):
        quotation = self._booking(self.friend_a, confirm=False)
        pending = self._booking(self.friend_b)
        frozen = self._booking(self.father)
        self._pay(self._invoice_deposit(frozen))
        self.env.flush_all()
        Forecast = self.env['travel.forecast.report']
        rows = {r.order_id: r for r in Forecast.search([('trip_id', '=', self.trip.id)])}
        total = 1021.0
        # quotation: win rate 50%
        self.assertAlmostEqual(rows[quotation].expected_revenue, total * 0.5)
        # deposit pending: 20% cancellation, nothing paid
        self.assertAlmostEqual(rows[pending].expected_revenue, total * 0.8)
        # deposit paid: 10% cancellation, deposit retained if cancelled
        self.assertAlmostEqual(rows[frozen].expected_revenue, total * 0.9 + 300 * 0.1)
        self.assertAlmostEqual(rows[frozen].expected_cost, 800 * 0.9)
        # cancelled bookings contribute with the retained penalty
        self.env['travel.booking.cancel'].create({
            'sale_order_id': frozen.id, 'reason': "x",
            'cancel_date': self.trip.date_start - timedelta(days=80)}).action_confirm()
        self.env.flush_all()
        self.env.invalidate_all()
        row = Forecast.search([('order_id', '=', frozen.id)])
        self.assertEqual(row.booking_state, 'cancelled')
        self.assertAlmostEqual(row.expected_revenue, 300.0)
        # excluding quotations
        self.company.travel_forecast_include_quotations = False
        self.env.flush_all()
        self.assertFalse(Forecast.search([('order_id', '=', quotation.id)]))

    def test_06_family_group_single_invoice(self):
        group = self.env['travel.group'].create({
            'name': "Family", 'trip_id': self.trip.id, 'group_type': 'family',
            'leader_id': self.father.id,
            'member_ids': [Command.set((self.father | self.mother | self.child).ids)],
        })
        group.action_create_bookings()
        self.assertEqual(len(group.sale_order_ids), 1)
        order = group.sale_order_ids
        self.assertEqual(order.partner_id, self.father)
        self.assertEqual(order.travel_pax_count, 3)
        order.action_confirm()
        group.action_create_invoices()
        invoices = self.env['account.move'].search([('travel_group_id', '=', group.id)])
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices.partner_id, self.father)

    def test_07_friends_group_invoice_per_member(self):
        group = self.env['travel.group'].create({
            'name': "Friends", 'trip_id': self.trip.id, 'group_type': 'friends',
            'leader_id': self.friend_a.id,
            'member_ids': [Command.set((self.friend_a | self.friend_b).ids)],
        })
        group.action_create_bookings()
        self.assertEqual(len(group.sale_order_ids), 2)
        self.assertEqual(group.sale_order_ids.partner_id, self.friend_a | self.friend_b)
        # running it again does not duplicate bookings
        group.action_create_bookings()
        self.assertEqual(len(group.sale_order_ids), 2)
        group.sale_order_ids.action_confirm()
        group.action_create_invoices()
        invoices = self.env['account.move'].search([('travel_group_id', '=', group.id)])
        self.assertEqual(len(invoices), 2)
        self.assertEqual(invoices.partner_id, self.friend_a | self.friend_b)
        self.assertEqual(group.invoice_count, 2)

    def test_08_profitability(self):
        order = self._booking(self.father)
        invoice = order._create_invoices(final=True)
        invoice.action_post()
        supplier = self.env['res.partner'].create({
            'name': "Operator", 'is_company': True, 'vat': '30714295698',
            'l10n_latam_identification_type_id': self.env.ref('l10n_ar.it_cuit').id,
            'l10n_ar_afip_responsibility_type_id': self.env.ref('l10n_ar.res_IVARI').id,
        })
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': supplier.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_ar.dc_a_f').id,
            'trip_id': self.trip.id,
            'invoice_date': self.today,
            'l10n_latam_document_number': '0001-00000001',
            'invoice_line_ids': [Command.create({
                'name': "Operator", 'quantity': 1, 'price_unit': 700.0,
                'tax_ids': [Command.set(self.env['account.tax'].search([
                    ('company_id', '=', self.company.id), ('type_tax_use', '=', 'purchase'),
                    ('tax_group_id.l10n_ar_vat_afip_code', '=', '1')], limit=1).ids)]})],
        })
        bill.action_post()
        self.env.flush_all()
        values = self.trip._travel_profitability_values()[self.trip.id]
        self.assertAlmostEqual(values['gross'], 1021.0)
        self.assertAlmostEqual(values['vat'], 21.0)
        self.assertAlmostEqual(values['revenue'], 1000.0)
        self.assertAlmostEqual(values['cost'], 700.0)
        self.assertAlmostEqual(values['iibb'], 50.0)
        self.assertAlmostEqual(values['net'], 250.0)

    def test_09_document_state(self):
        international = self.trip.copy({'country_id': self.env.ref('base.do').id,
                                        'trip_type': 'international'})
        order = self.env['sale.order'].create({
            'partner_id': self.father.id, 'trip_id': international.id,
            'travel_passenger_ids': [Command.create({'partner_id': self.father.id})],
        })
        passenger = order.travel_passenger_ids
        self.assertEqual(passenger.document_state, 'missing')
        self.father.write({'passport_number': 'AAA111111',
                           'passport_expiry_date': international.date_end + timedelta(days=30)})
        self.assertEqual(passenger.document_state, 'expiring')
        self.father.passport_expiry_date = international.date_end + timedelta(days=400)
        self.assertEqual(passenger.document_state, 'ok')

    def test_10_birthday_email(self):
        template = self.env.ref('odossey_travel.mail_template_birthday')
        today = date(2026, 9, 27)
        self.father.write({'email': 'father@example.com', 'birthdate': date(1980, 9, 27)})
        self.mother.write({'email': 'mother@example.com', 'birthdate': date(1980, 9, 28)})
        self.company.travel_birthday_template_id = template
        Partner = self.env['res.partner']
        with patch('odoo.fields.Date.context_today', return_value=today), \
                patch.object(type(template), 'send_mail', autospec=True) as send_mail:
            Partner._cron_travel_send_birthday_emails()
            sent_to = {call.args[1] for call in send_mail.call_args_list}
            self.assertIn(self.father.id, sent_to)
            self.assertNotIn(self.mother.id, sent_to)
            self.assertEqual(self.father.travel_birthday_last_sent, today)
            send_mail.reset_mock()
            Partner._cron_travel_send_birthday_emails()
            self.assertNotIn(self.father.id, {c.args[1] for c in send_mail.call_args_list},
                             "Only one greeting per year")

    def test_11_crm_quotation_context(self):
        lead = self.env['crm.lead'].create({'name': "Lead", 'type': 'opportunity',
                                            'partner_id': self.father.id,
                                            'trip_id': self.trip.id})
        context = lead._prepare_opportunity_quotation_context()
        self.assertEqual(context['default_trip_id'], self.trip.id)

    def test_12_calendar_entry(self):
        entry = self.env['travel.activity'].search([('trip_id', '=', self.trip.id),
                                                    ('activity_type', '=', 'trip')])
        self.assertEqual(len(entry), 1)
        self.trip.date_end = self.trip.date_end + timedelta(days=2)
        self.assertEqual(entry.stop.date(), self.trip.date_end)
        order = self._booking(self.father | self.mother)
        self.assertEqual(entry.passenger_partner_ids, self.father | self.mother)
        self.assertTrue(order)
