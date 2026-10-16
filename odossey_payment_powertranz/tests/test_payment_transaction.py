# Part of Odossey. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from werkzeug import urls

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.odossey_payment_powertranz.tests.common import MAKE_REQUEST, PowerTranzCommon

LOGGERS = (
    'odoo.addons.odossey_payment_powertranz.models.payment_transaction',
    'odoo.addons.payment.models.payment_transaction',
)


@tagged('post_install', '-at_install')
class TestPaymentTransaction(PowerTranzCommon):

    # === Redirect (spi/sale) === #

    def test_rendering_values_start_hosted_page(self):
        tx = self._create_transaction('redirect')
        with patch(MAKE_REQUEST, return_value=self.spi_sale_response) as mock:
            processing_values = tx._get_processing_values()

        endpoint = mock.call_args.args[0]
        payload = mock.call_args.kwargs['payload']
        self.assertEqual(endpoint, 'spi/sale')
        self.assertEqual(payload['TransactionIdentifier'], tx.provider_reference)
        self.assertEqual(payload['TotalAmount'], 150.25)
        self.assertIsInstance(payload['TotalAmount'], float)
        self.assertEqual(payload['CurrencyCode'], '840')
        self.assertTrue(payload['ThreeDSecure'])
        self.assertEqual(payload['OrderIdentifier'], tx.reference)
        self.assertEqual(payload['ExtendedData']['HostedPage'], {
            'PageSet': 'PTZ/MyPageSet', 'PageName': 'MyPage',
        })
        self.assertEqual(payload['ExtendedData']['ThreeDSecure']['ChallengeWindowSize'], 5)
        response_url = urls.url_parse(payload['ExtendedData']['MerchantResponseUrl'])
        self.assertEqual(response_url.path, '/payment/powertranz/return')
        query = response_url.decode_query()
        self.assertEqual(query['reference'], tx.reference)
        self.assertEqual(
            query['access_token'],
            self._generate_test_access_token(tx.reference, tx.provider_reference),
        )

        form = self._extract_values_from_html_form(processing_values['redirect_form_html'])
        self.assertTrue(form['action'].endswith('/payment/powertranz/redirect'))
        self.assertEqual(form['method'], 'get')
        self.assertEqual(form['inputs']['reference'], tx.reference)
        self.assertEqual(form['inputs']['access_token'], query['access_token'])
        self.assertEqual(tx.powertranz_redirect_data, self.spi_sale_response['RedirectData'])
        self.assertEqual(tx.powertranz_spi_token, self.spi_token)

    def test_each_attempt_gets_a_new_guid(self):
        tx = self._create_transaction('redirect')
        with patch(MAKE_REQUEST, return_value=self.spi_sale_response):
            tx._get_processing_values()
        tx2 = self._create_transaction('redirect', reference='S00042-2')
        with patch(MAKE_REQUEST, return_value=self.spi_sale_response):
            tx2._get_processing_values()
        self.assertTrue(tx.provider_reference)
        self.assertNotEqual(tx.provider_reference, tx2.provider_reference)

    def test_no_3ds_payload(self):
        self.provider.powertranz_use_3ds = False
        tx = self._create_transaction('redirect')
        with patch(MAKE_REQUEST, return_value=self.spi_sale_response) as mock:
            tx._get_processing_values()
        payload = mock.call_args.kwargs['payload']
        self.assertFalse(payload['ThreeDSecure'])
        self.assertNotIn('ThreeDSecure', payload['ExtendedData'])

    @mute_logger(*LOGGERS)
    def test_spi_sale_error_raises(self):
        tx = self._create_transaction('redirect')
        error = {
            'Approved': False, 'IsoResponseCode': '12', 'ResponseMessage': 'Invalid transaction',
            'Errors': [{'Code': '343', 'Message': 'Invalid merchant'}],
        }
        with patch(MAKE_REQUEST, return_value=error), \
                self.assertRaisesRegex(ValidationError, 'Invalid merchant'):
            tx._get_processing_values()

    def test_billing_address_is_cleaned(self):
        self.partner.write({
            'name': 'José Ñúñez Pérez', 'street': 'Calle 50, Edificio Torre Ñ #12', 'city': 'Panamá',
            'zip': '08-01', 'phone': '+507 6123-4567', 'country_id': self.env.ref('base.pa').id,
        })
        tx = self._create_transaction('redirect')
        address = tx._powertranz_prepare_billing_address()
        self.assertEqual(address['FirstName'], 'Jose Nunez')
        self.assertEqual(address['LastName'], 'Perez')
        self.assertEqual(address['City'], 'Panama')
        self.assertRegex(address['Line1'], r"^[a-zA-Z0-9\-' .]*$")
        self.assertLessEqual(len(address['Line1']), 30)
        self.assertEqual(address['PostalCode'], '0801')
        self.assertEqual(address['PhoneNumber'], '50761234567')
        try:
            import pycountry  # noqa: F401
            self.assertEqual(address['CountryCode'], '591')
        except ImportError:
            self.assertNotIn('CountryCode', address)

    # === Hosted page callback === #

    def _mock_requests(self, responses):
        """ Patch the API helper and answer by endpoint; record the calls. """
        calls = []

        def make_request(provider, endpoint, payload=None, method='POST', spi_token=None):
            calls.append((endpoint, payload, spi_token))
            response = responses[endpoint]
            if isinstance(response, Exception):
                raise response
            return response
        return patch(MAKE_REQUEST, autospec=True, side_effect=make_request), calls

    def test_3ds_success_completes_payment(self):
        tx = self._create_redirect_tx()
        patcher, calls = self._mock_requests({'spi/payment': self.payment_approved})
        with patcher:
            tx._powertranz_handle_hpp_callback(self.callback_3ds_ok)
        self.assertEqual(calls, [('spi/payment', None, self.spi_token)])
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, self.guid)
        self.assertEqual(tx.payment_method_id, self.env.ref('payment.payment_method_visa'))
        self.assertIn('123456', tx.state_message)
        self.assertFalse(tx.powertranz_redirect_data)
        self.assertFalse(tx.powertranz_spi_token)

    def test_hp0_without_3ds_completes_payment(self):
        tx = self._create_redirect_tx()
        callback = dict(self.callback_3ds_ok, IsoResponseCode='HP0', RiskManagement={})
        patcher, calls = self._mock_requests({'spi/payment': self.payment_approved})
        with patcher:
            tx._powertranz_handle_hpp_callback(callback)
        self.assertEqual(len(calls), 1)
        self.assertEqual(tx.state, 'done')

    def test_stored_token_is_preferred_over_posted_one(self):
        tx = self._create_redirect_tx()
        callback = dict(self.callback_3ds_ok, SpiToken='forged-token')
        patcher, calls = self._mock_requests({'spi/payment': self.payment_approved})
        with patcher:
            tx._powertranz_handle_hpp_callback(callback)
        self.assertEqual(calls[0][2], self.spi_token)

    @mute_logger(*LOGGERS)
    def test_3ds_failed_does_not_complete_payment(self):
        for status in ('N', 'R'):
            tx = self._create_redirect_tx(reference=f'S00042-{status}')
            callback = dict(self.callback_3ds_ok, RiskManagement={'ThreeDSecure': {
                'AuthenticationStatus': status,
            }})
            patcher, calls = self._mock_requests({})
            with patcher:
                tx._powertranz_handle_hpp_callback(callback)
            self.assertFalse(calls, "spi/payment must not be called when 3DS failed")
            self.assertEqual(tx.state, 'error')
            self.assertIn(f'status {status}', tx.state_message)

    @mute_logger(*LOGGERS)
    def test_3ds_unavailable_follows_setting(self):
        callback = dict(self.callback_3ds_ok, RiskManagement={'ThreeDSecure': {
            'AuthenticationStatus': 'U',
        }})
        tx = self._create_redirect_tx(reference='S00042-U1')
        patcher, calls = self._mock_requests({})
        with patcher:
            tx._powertranz_handle_hpp_callback(callback)
        self.assertEqual(tx.state, 'error')

        self.provider.powertranz_allow_3ds_unavailable = True
        tx = self._create_redirect_tx(reference='S00042-U2')
        approved = dict(self.payment_approved, OrderIdentifier='S00042-U2')
        patcher, calls = self._mock_requests({'spi/payment': approved})
        with patcher:
            tx._powertranz_handle_hpp_callback(callback)
        self.assertEqual(tx.state, 'done')

    @mute_logger(*LOGGERS)
    def test_card_without_3ds_follows_setting(self):
        callback = dict(self.callback_3ds_ok, IsoResponseCode='3D1', RiskManagement={})
        tx = self._create_redirect_tx(reference='S00042-A')
        approved = dict(self.payment_approved, OrderIdentifier='S00042-A')
        patcher, calls = self._mock_requests({'spi/payment': approved})
        with patcher:
            tx._powertranz_handle_hpp_callback(callback)
        self.assertEqual(tx.state, 'done')

        self.provider.powertranz_allow_non_3ds_cards = False
        tx = self._create_redirect_tx(reference='S00042-B')
        patcher, calls = self._mock_requests({})
        with patcher:
            tx._powertranz_handle_hpp_callback(callback)
        self.assertFalse(calls)
        self.assertEqual(tx.state, 'error')

    @mute_logger(*LOGGERS)
    def test_unknown_callback_code_sets_error(self):
        tx = self._create_redirect_tx()
        callback = dict(self.callback_3ds_ok, IsoResponseCode='3D3', ResponseMessage='3DS error')
        patcher, calls = self._mock_requests({})
        with patcher:
            tx._powertranz_handle_hpp_callback(callback)
        self.assertFalse(calls)
        self.assertEqual(tx.state, 'error')
        self.assertIn('3DS error', tx.state_message)

    @mute_logger(*LOGGERS)
    def test_declined_payment_sets_error(self):
        tx = self._create_redirect_tx()
        patcher, _calls = self._mock_requests({'spi/payment': self.payment_declined})
        with patcher:
            tx._powertranz_handle_hpp_callback(self.callback_3ds_ok)
        self.assertEqual(tx.state, 'error')
        self.assertIn('Do not honor', tx.state_message)
        self.assertIn('[05]', tx.state_message)

    @mute_logger(*LOGGERS)
    def test_approved_but_mismatching_data_sets_error(self):
        cases = {
            'amount': {'TotalAmount': 0.01},
            'currency': {'CurrencyCode': '978'},
            'transaction identifier': {'TransactionIdentifier': 'other-guid'},
            'order identifier': {'OrderIdentifier': 'S99999'},
        }
        for index, (field, values) in enumerate(cases.items()):
            tx = self._create_redirect_tx(reference=f'S00042-M{index}')
            response = dict(self.payment_approved, OrderIdentifier=tx.reference)
            response.update(values)
            patcher, _calls = self._mock_requests({'spi/payment': response})
            with patcher:
                tx._powertranz_handle_hpp_callback(self.callback_3ds_ok)
            self.assertEqual(tx.state, 'error', field)
            self.assertIn(field, tx.state_message)

    def test_posted_guid_mismatch_raises(self):
        tx = self._create_redirect_tx()
        callback = dict(self.callback_3ds_ok, TransactionIdentifier='other-guid')
        patcher, calls = self._mock_requests({})
        with patcher, self.assertRaises(ValidationError):
            tx._powertranz_handle_hpp_callback(callback)
        self.assertFalse(calls)
        self.assertEqual(tx.state, 'draft')

    def test_already_processed_tx_is_skipped(self):
        tx = self._create_redirect_tx(state='done')
        patcher, calls = self._mock_requests({})
        with patcher:
            tx._powertranz_handle_hpp_callback(self.callback_3ds_ok)
        self.assertFalse(calls)
        self.assertEqual(tx.state, 'done')

    @mute_logger(*LOGGERS)
    def test_expired_token_checks_gateway_status(self):
        """ A lost response of a first callback must not fail an approved sale. """
        tx = self._create_redirect_tx()
        lookup = {
            'TransactionIdentifier': self.guid, 'TransactionType': 2, 'TotalAmount': self.amount,
            'CurrencyCode': '840', 'IsoResponseCode': '00', 'ResponseMessage': 'Approved',
            'AuthorizationCode': '654321', 'Rrn': '1234',
            'OrderSummary': {'OrderIdentifier': self.reference},
        }
        patcher, calls = self._mock_requests({
            'spi/payment': ValidationError('HTTP 400'), f'transactions/{self.guid}': lookup,
        })
        with patcher:
            tx._powertranz_handle_hpp_callback(self.callback_3ds_ok)
        self.assertEqual([c[0] for c in calls], ['spi/payment', f'transactions/{self.guid}'])
        self.assertEqual(tx.state, 'done')
        self.assertIn('654321', tx.state_message)

    @mute_logger(*LOGGERS)
    def test_expired_token_and_no_sale_sets_error(self):
        tx = self._create_redirect_tx()
        patcher, _calls = self._mock_requests({
            'spi/payment': ValidationError('HTTP 400'),
            f'transactions/{self.guid}': ValidationError('HTTP 404'),
        })
        with patcher:
            tx._powertranz_handle_hpp_callback(self.callback_3ds_ok)
        self.assertEqual(tx.state, 'error')
        self.assertIn('session expired', tx.state_message)

    def test_get_tx_from_notification_data(self):
        tx = self._create_redirect_tx()
        found = self.env['payment.transaction']._get_tx_from_notification_data(
            'powertranz', {'reference': tx.reference}
        )
        self.assertEqual(found, tx)
        with self.assertRaises(ValidationError):
            self.env['payment.transaction']._get_tx_from_notification_data(
                'powertranz', {'reference': 'unknown'}
            )
        with self.assertRaises(ValidationError):
            self.env['payment.transaction']._get_tx_from_notification_data('powertranz', {})
