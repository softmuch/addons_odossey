# Part of Odossey. See LICENSE file for full copyright and licensing details.

import json
from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.odossey_payment_powertranz.tests.common import PowerTranzCommon

REQUESTS = 'odoo.addons.odossey_payment_powertranz.models.payment_provider.requests.request'


@tagged('post_install', '-at_install')
class TestPaymentProvider(PowerTranzCommon):

    def test_feature_support(self):
        self.assertEqual(self.provider.support_refund, 'partial')
        self.assertFalse(self.provider.support_manual_capture)
        self.assertFalse(self.provider.support_tokenization)

    def test_card_payment_methods_activated(self):
        """ Enabling the provider must activate the card and its main brands. """
        card = self.env.ref('payment.payment_method_card')
        self.assertTrue(card.active)
        self.assertTrue(self.env.ref('payment.payment_method_visa').active)
        self.assertTrue(self.env.ref('payment.payment_method_mastercard').active)

    def test_compatible_with_usd_not_with_unsupported_currency(self):
        compatible = self.env['payment.provider']._get_compatible_providers(
            self.company_id, self.partner.id, self.amount, currency_id=self.currency_usd.id,
        )
        self.assertIn(self.provider, compatible)
        jpy = self._prepare_currency('JPY')
        compatible = self.env['payment.provider']._get_compatible_providers(
            self.company_id, self.partner.id, self.amount, currency_id=jpy.id,
        )
        self.assertNotIn(self.provider, compatible)

    def test_page_set_prefix(self):
        self.assertEqual(self.provider._powertranz_get_page_set(), 'PTZ/MyPageSet')
        self.provider.powertranz_page_set = ' ptz/Other '
        self.assertEqual(self.provider._powertranz_get_page_set(), 'ptz/Other')

    def test_api_url_by_state(self):
        self.assertEqual(self.provider._powertranz_get_api_url(), 'https://staging.ptranz.com/api/')
        self.provider.state = 'enabled'
        self.assertEqual(self.provider._powertranz_get_api_url(), 'https://gateway.ptranz.com/api/')
        self.provider.powertranz_api_url = 'https://other.ptranz.com/api'
        self.assertEqual(self.provider._powertranz_get_api_url(), 'https://other.ptranz.com/api/')

    def _mock_response(self, status=200, content=None):
        response = MagicMock()
        response.status_code = status
        response.text = json.dumps(content) if content is not None else ''
        response.json.return_value = content
        if status >= 400:
            import requests
            response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        return response

    def test_request_headers_and_json_payload(self):
        with patch(REQUESTS, return_value=self._mock_response(content={'Approved': True})) as mock:
            self.provider._powertranz_make_request('refund', payload={'Refund': True})
        method, url = mock.call_args.args
        kwargs = mock.call_args.kwargs
        self.assertEqual((method, url), ('POST', 'https://staging.ptranz.com/api/refund'))
        self.assertEqual(kwargs['headers']['PowerTranz-PowerTranzId'], '88800001')
        self.assertEqual(kwargs['headers']['PowerTranz-PowerTranzPassword'], 'secret-password')
        self.assertEqual(kwargs['headers']['Content-Type'], 'application/json')
        self.assertNotIn('PowerTranz-GatewayKey', kwargs['headers'])
        self.assertEqual(json.loads(kwargs['data']), {'Refund': True})

    def test_spi_payment_body_is_quoted_token(self):
        """ The spi/payment body is the token as a JSON string literal, with the quotes. """
        with patch(REQUESTS, return_value=self._mock_response(content={'Approved': True})) as mock:
            self.provider._powertranz_make_request('spi/payment', spi_token='abc-123')
        self.assertEqual(mock.call_args.kwargs['data'], '"abc-123"')

    @mute_logger('odoo.addons.odossey_payment_powertranz.models.payment_provider')
    def test_http_error_raises(self):
        with patch(REQUESTS, return_value=self._mock_response(status=400)), \
                self.assertRaises(ValidationError):
            self.provider._powertranz_make_request('spi/payment', spi_token='expired')

    def test_get_request_has_no_body(self):
        with patch(REQUESTS, return_value=self._mock_response(content={})) as mock:
            self.provider._powertranz_make_request(f'transactions/{self.guid}', method='GET')
        self.assertEqual(mock.call_args.args[0], 'GET')
        self.assertIsNone(mock.call_args.kwargs['data'])
