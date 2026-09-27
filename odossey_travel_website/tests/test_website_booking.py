from datetime import date, timedelta

from odoo import fields
from odoo.fields import Command
from odoo.http import Request
from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestWebsiteBooking(AccountTestInvoicingCommon, HttpCase):

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
        cls.company.l10n_ar_afip_start_date = date(2020, 1, 1)
        cls.website = cls.env['website'].create({'name': "Travel test", 'company_id': cls.company.id})
        tax = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id), ('type_tax_use', '=', 'sale'),
            ('tax_group_id.l10n_ar_vat_afip_code', '=', '2')], limit=1)
        cls.service = cls.env['product.product'].create({
            'name': "Package", 'type': 'service', 'invoice_policy': 'order',
            'taxes_id': [Command.set(tax.ids)]})
        cls.today = fields.Date.context_today(cls.env.user)
        cls.trip = cls.env['travel.trip'].create({
            'name': "Web trip",
            'destination': "Ushuaia",
            'country_id': cls.env.ref('base.ar').id,
            'company_id': cls.company.id,
            'currency_id': cls.company.currency_id.id,
            'date_start': cls.today + timedelta(days=120),
            'date_end': cls.today + timedelta(days=125),
            'capacity': 4,
            'deposit_type': 'percent',
            'deposit_percent': 25.0,
            'balance_due_days': 30,
            'component_ids': [Command.create({'product_id': cls.service.id, 'price_unit': 1000.0,
                                              'cost_unit': 800.0})],
        })
        cls.trip.action_open()
        cls.trip.is_published = True
        demo_method = cls.env.ref('payment_demo.payment_method_demo', raise_if_not_found=False)
        cls.provider = demo_method and cls.env['payment.provider'].create({
            'name': "Demo test", 'code': 'demo', 'state': 'test', 'is_published': True,
            'company_id': cls.company.id, 'payment_method_ids': [Command.set(demo_method.ids)],
        })

    def _book(self, pax=2, **extra):
        data = {
            'csrf_token': Request.csrf_token(self),
            'pax': pax,
            'name': "Web Customer", 'email': 'web.customer@example.com', 'vat': '30999888',
            'holder_travels': '1', 'accept_conditions': '1', 'room_type': 'double',
        }
        for i in range(pax):
            data[f'passenger_{i}_name'] = f"Passenger {i}"
            data[f'passenger_{i}_vat'] = f'4000000{i}'
        data.update(extra)
        url = f"{self.trip.website_url}/reservar"
        response = self.url_open(url, data=data, allow_redirects=False)
        return response

    def _last_order(self):
        return self.env['sale.order'].search([('trip_id', '=', self.trip.id)], order='id desc',
                                             limit=1)

    def _pay(self, order, amount):
        tx = self.env['payment.transaction'].sudo().create({
            'provider_id': self.provider.id,
            'payment_method_id': self.provider.payment_method_ids[:1].id,
            'amount': amount,
            'currency_id': order.currency_id.id,
            'partner_id': order.partner_id.id,
            'sale_order_ids': [Command.set(order.ids)],
            'reference': f"{order.name}-{amount}",
        })
        tx._set_done()
        tx._post_process()
        return tx

    def _setup_website(self):
        self.website.domain = False
        self.env['website'].search([('id', '!=', self.website.id)]).sequence = 100
        self.website.sequence = 1
        self.authenticate(None, None)

    def test_01_catalogue_and_booking(self):
        self._setup_website()
        response = self.url_open('/viajes')
        self.assertEqual(response.status_code, 200)
        self.assertIn("Web trip", response.text)
        self.assertEqual(self.url_open(self.trip.website_url).status_code, 200)
        response = self._book(pax=2)
        self.assertEqual(response.status_code, 303, response.text[:500])
        order = self._last_order()
        self.assertTrue(order.travel_web_booking)
        self.assertEqual(order.travel_pax_count, 2)
        self.assertEqual(order.amount_total, 2000.0)
        self.assertTrue(order.require_payment)
        self.assertAlmostEqual(order._get_prepayment_required_amount(), 500.0)
        self.assertIn('/my/orders/', response.headers['Location'])
        # seats are held by the unpaid online quotation
        self.assertEqual(self.trip.web_seats_available, 2)

    def test_02_deposit_then_balance_online(self):
        if not self.provider:
            self.skipTest("payment_demo not installed")
        self._setup_website()
        self._book(pax=2)
        order = self._last_order()
        tx = self._pay(order, 500.0)
        self.assertEqual(order.state, 'sale')
        self.assertTrue(order.travel_price_frozen)
        self.assertEqual(order.travel_booking_state, 'deposit')
        self.assertAlmostEqual(order.travel_amount_paid, 500.0)
        invoices = order.invoice_ids.filtered(lambda m: m.state == 'posted')
        self.assertEqual(len(invoices), 1)
        self.assertEqual(tx.invoice_ids, invoices)
        self.assertIn(tx.payment_id.state, ('in_process', 'paid'))
        # the balance is paid later from the portal
        self._pay(order, 1500.0)
        self.assertEqual(order.travel_booking_state, 'paid')
        self.assertAlmostEqual(order.travel_amount_due, 0.0)
        self.assertEqual(len(order.invoice_ids.filtered(lambda m: m.state == 'posted')), 2)
        self.assertEqual(order.invoice_status, 'invoiced')

    def test_03_full_payment(self):
        if not self.provider:
            self.skipTest("payment_demo not installed")
        self._setup_website()
        self._book(pax=1)
        order = self._last_order()
        self._pay(order, 1000.0)
        self.assertEqual(order.travel_booking_state, 'paid')
        self.assertEqual(order.invoice_status, 'invoiced')

    def test_04_no_deposit_after_due_date(self):
        self._setup_website()
        self.trip.write({'date_start': self.today + timedelta(days=10),
                         'date_end': self.today + timedelta(days=12)})
        self._book(pax=1)
        order = self._last_order()
        self.assertEqual(order.prepayment_percent, 1.0)
        self.assertEqual(order._get_prepayment_required_amount(), order.amount_total)

    @mute_logger('odoo.addons.odossey_travel_website.models.payment_transaction')
    def test_05_overbooking_does_not_break_payment(self):
        if not self.provider:
            self.skipTest("payment_demo not installed")
        self._setup_website()
        self._book(pax=2)
        order = self._last_order()
        # the trip gets full in the back-office meanwhile
        other = self.env['sale.order'].create({
            'partner_id': self.partner_a.id, 'trip_id': self.trip.id,
            'travel_passenger_ids': [Command.create({'partner_id': self.partner_a.id}),
                                     Command.create({'partner_id': self.partner_b.id}),
                                     Command.create({'partner_id': self.company.partner_id.id})],
        })
        other._travel_load_services()
        other.action_confirm()
        self._pay(order, 500.0)
        self.assertIn(order.state, ('draft', 'sent'))
        self.assertTrue(order.activity_ids)

    def test_06_bookings_blocked_when_full(self):
        self._setup_website()
        response = self._book(pax=5)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._last_order())

    def test_07_withdrawal_button(self):
        self._setup_website()
        self._book(pax=1)
        order = self._last_order()
        response = self.url_open('/viajes/arrepentimiento', data={
            'csrf_token': Request.csrf_token(self),
            'reference': order.name, 'email': 'web.customer@example.com', 'reason': "Changed plans",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(order.travel_withdrawal_date)
        self.assertTrue(order.activity_ids)

    def test_08_booking_tour(self):
        self._setup_website()
        self.start_tour('/viajes', 'odossey_travel_website_booking')
        order = self._last_order()
        self.assertEqual(order.partner_id.name, "Tour Customer")
        self.assertEqual(order.travel_pax_count, 2)

    def test_demo_website_data(self):
        Trip = self.env['travel.trip'].with_company(self.company)
        Trip._travel_load_demo_data()
        trips = Trip.search([('company_id', '=', self.company.id), ('id', '!=', self.trip.id)])
        published = trips.filtered('is_published')
        self.assertTrue(published.filtered('web_bookable'))
        self.assertTrue(published.filtered(lambda t: not t.web_seats_available),
                        "A sold out trip is published")
        self.assertIn('trip', published.mapped('web_currency'))
        self.assertIn(False, published.mapped('web_allow_deposit'))
        orders = self.env['sale.order'].search([('trip_id', 'in', trips.ids),
                                                ('travel_web_booking', '=', True)])
        self.assertEqual(set(orders.mapped('state')), {'draft', 'sale'})
        self.assertTrue(orders.filtered('travel_withdrawal_date'))
        self.assertTrue(orders.filtered(lambda o: o.state == 'draft'
                                        and o.validity_date < self.today),
                        "An expired online quotation is included")
        caribe = orders.filtered(lambda o: o.trip_id.currency_id != o.currency_id)
        self.assertEqual(caribe.currency_id, self.company.currency_id,
                         "A USD trip is sold online in pesos")

    def test_catalogue_trip_currency_public(self):
        """A published trip paid online in its own currency renders for visitors."""
        usd = self.env.ref('base.USD')
        usd.active = True
        self.trip.write({'currency_id': usd.id, 'web_currency': 'trip'})
        self._setup_website()
        response = self.url_open('/viajes')
        self.assertEqual(response.status_code, 200)
        self.assertIn("Web trip", response.text)
        response = self.url_open(self.trip.website_url)
        self.assertEqual(response.status_code, 200)

