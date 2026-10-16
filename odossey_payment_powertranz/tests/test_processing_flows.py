# Part of Odossey. See LICENSE file for full copyright and licensing details.

import json
from unittest.mock import patch

from werkzeug import urls

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.odossey_payment_powertranz.controllers.main import PowerTranzController
from odoo.addons.odossey_payment_powertranz.tests.common import MAKE_REQUEST, PowerTranzCommon

CONTROLLER_LOGGER = 'odoo.addons.odossey_payment_powertranz.controllers.main'


@tagged('post_install', '-at_install')
class TestProcessingFlows(PowerTranzCommon, PaymentHttpCommon):

    def _token(self, tx):
        return self._generate_test_access_token(tx.reference, tx.provider_reference)

    def _return_url(self, tx, access_token=None):
        return self._build_url(PowerTranzController._return_url) + '?' + urls.url_encode({
            'reference': tx.reference, 'access_token': access_token or self._token(tx),
        })

    # === Redirect route === #

    def test_redirect_route_serves_hosted_page(self):
        tx = self._create_redirect_tx()
        response = self._make_http_get_request(
            self._build_url(PowerTranzController._redirect_url),
            params={'reference': tx.reference, 'access_token': self._token(tx)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, self.spi_sale_response['RedirectData'])
        self.assertIn('text/html', response.headers['Content-Type'])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    @mute_logger(CONTROLLER_LOGGER)
    def test_redirect_route_refuses_bad_token(self):
        tx = self._create_redirect_tx()
        response = self._make_http_get_request(
            self._build_url(PowerTranzController._redirect_url),
            params={'reference': tx.reference, 'access_token': 'bad'},
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('staging.ptranz.com', response.text)

    def test_redirect_route_after_processing_goes_to_status(self):
        tx = self._create_redirect_tx(state='done')
        response = self._make_http_get_request(
            self._build_url(PowerTranzController._redirect_url),
            params={'reference': tx.reference, 'access_token': self._token(tx)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.url.endswith('/payment/status'))

    # === Return route (MerchantResponseUrl) === #

    def test_return_route_completes_payment(self):
        tx = self._create_redirect_tx()
        with patch(MAKE_REQUEST, return_value=self.payment_approved) as mock:
            response = self._make_http_post_request(
                self._return_url(tx), data=self._build_callback_form(self.callback_3ds_ok),
            )
        self.assertEqual(mock.call_args.args[0], 'spi/payment')
        self.assertEqual(mock.call_args.kwargs['spi_token'], self.spi_token)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.url.endswith('/payment/status'))
        tx.invalidate_recordset()
        self.assertEqual(tx.state, 'done')

    def test_return_route_lowercase_fields(self):
        tx = self._create_redirect_tx()
        form = {
            'response': json.dumps(self.callback_3ds_ok),
            'spiToken': self.spi_token,
            'transactionIdentifier': self.guid,
        }
        with patch(
            'odoo.addons.odossey_payment_powertranz.models.payment_transaction.PaymentTransaction'
            '._powertranz_handle_hpp_callback'
        ) as handle_mock:
            self._make_http_post_request(self._return_url(tx), data=form)
        self.assertEqual(handle_mock.call_count, 1)
        callback = handle_mock.call_args.args[0]
        self.assertEqual(callback['IsoResponseCode'], '3D0')
        self.assertEqual(callback['SpiToken'], self.spi_token)

    @mute_logger(CONTROLLER_LOGGER)
    def test_return_route_refuses_bad_token(self):
        tx = self._create_redirect_tx()
        with patch(MAKE_REQUEST) as mock:
            response = self._make_http_post_request(
                self._return_url(tx, access_token='forged'),
                data=self._build_callback_form(self.callback_3ds_ok),
            )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(mock.called)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, 'draft')

    @mute_logger(CONTROLLER_LOGGER)
    def test_return_route_invalid_json_keeps_tx_draft(self):
        tx = self._create_redirect_tx()
        with patch(MAKE_REQUEST) as mock:
            response = self._make_http_post_request(self._return_url(tx), data={'Response': '{bad'})
        self.assertFalse(mock.called)
        self.assertTrue(response.url.endswith('/payment/status'))
        tx.invalidate_recordset()
        self.assertEqual(tx.state, 'draft')

    def test_double_callback_completes_once(self):
        tx = self._create_redirect_tx()
        form = self._build_callback_form(self.callback_3ds_ok)
        with patch(MAKE_REQUEST, return_value=self.payment_approved) as mock:
            self._make_http_post_request(self._return_url(tx), data=form)
            self._make_http_post_request(self._return_url(tx), data=form)
        self.assertEqual(mock.call_count, 1)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, 'done')
