# Part of Odossey. See LICENSE file for full copyright and licensing details.

import json

from odoo.addons.payment.tests.common import PaymentCommon

MAKE_REQUEST = (
    'odoo.addons.odossey_payment_powertranz.models.payment_provider.PaymentProvider'
    '._powertranz_make_request'
)


class PowerTranzCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency = cls.currency_usd
        cls.provider = cls._prepare_provider('powertranz', update_values={
            'powertranz_merchant_id': '88800001',
            'powertranz_password': 'secret-password',
            'powertranz_page_set': 'MyPageSet',
            'powertranz_page_name': 'MyPage',
            'powertranz_api_url': False,
            'powertranz_gateway_key': False,
            'powertranz_use_3ds': True,
            'powertranz_allow_non_3ds_cards': True,
            'powertranz_allow_3ds_unavailable': False,
        })
        cls.payment_method = cls.env.ref('payment.payment_method_card')
        cls.payment_method_id = cls.payment_method.id
        cls.amount = 150.25
        cls.reference = 'S00042-1'
        cls.guid = '40511888-ad35-4bba-8dcb-214f493e185c'
        cls.spi_token = '1gs2sfyhhi744o98f2uxmxd5w5jw7tbsflkth3rmvav520gqgto-iseenw5eb'

        cls.spi_sale_response = {
            'TransactionType': 2,
            'Approved': False,
            'TransactionIdentifier': cls.guid,
            'TotalAmount': cls.amount,
            'CurrencyCode': '840',
            'IsoResponseCode': 'SP4',
            'ResponseMessage': 'SPI Preprocessing complete',
            'OrderIdentifier': cls.reference,
            'RedirectData': '<!DOCTYPE html><html><body><form id="f" method="POST" '
                            'action="https://staging.ptranz.com/hpp"></form>'
                            '<script>document.getElementById("f").submit();</script></body></html>',
            'SpiToken': cls.spi_token,
        }
        cls.callback_3ds_ok = {
            'TransactionType': 2,
            'Approved': False,
            'TransactionIdentifier': cls.guid,
            'TotalAmount': cls.amount,
            'CurrencyCode': '840',
            'CardBrand': 'Visa',
            'IsoResponseCode': '3D0',
            'ResponseMessage': '3DS complete',
            'RiskManagement': {'ThreeDSecure': {
                'Eci': '05', 'AuthenticationStatus': 'Y', 'ResponseCode': '3D0',
            }},
            'OrderIdentifier': cls.reference,
            'SpiToken': cls.spi_token,
        }
        cls.payment_approved = {
            'TransactionType': 2,
            'Approved': True,
            'AuthorizationCode': '123456',
            'TransactionIdentifier': cls.guid,
            'TotalAmount': cls.amount,
            'CurrencyCode': '840',
            'RRN': '307522590956',
            'CardBrand': 'Visa',
            'IsoResponseCode': '00',
            'ResponseMessage': 'Transaction is approved',
            'OrderIdentifier': cls.reference,
        }
        cls.payment_declined = dict(
            cls.payment_approved, Approved=False, IsoResponseCode='05', ResponseMessage='Do not honor',
            AuthorizationCode=None,
        )
        cls.refund_guid = 'd9eb9bee-f99b-451a-a91c-f94dac725c12'
        cls.refund_approved = {
            'OriginalTrxnIdentifier': cls.guid,
            'TransactionType': 5,
            'Approved': True,
            'TransactionIdentifier': cls.refund_guid,
            'TotalAmount': 50.0,
            'CurrencyCode': '840',
            'RRN': '628914784716',
            'IsoResponseCode': '00',
            'ResponseMessage': 'Transaction is approved',
        }

    def _create_redirect_tx(self, **values):
        """ Create a transaction as it is after `spi/sale`: GUID, token and HTML stored. """
        tx = self._create_transaction('redirect', provider_reference=self.guid, **values)
        tx.write({
            'powertranz_redirect_data': self.spi_sale_response['RedirectData'],
            'powertranz_spi_token': self.spi_token,
        })
        return tx

    @staticmethod
    def _build_callback_form(callback):
        return {
            'Response': json.dumps(callback),
            'TransactionIdentifier': callback.get('TransactionIdentifier'),
            'SpiToken': callback.get('SpiToken'),
        }
