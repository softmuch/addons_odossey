# Part of Odossey. See LICENSE file for full copyright and licensing details.

import logging
import re
import unicodedata
import uuid

from werkzeug import urls

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_round
from odoo.tools.misc import hmac as hmac_tool

from odoo.addons.payment import utils as payment_utils
from odoo.addons.odossey_payment_powertranz import const
from odoo.addons.odossey_payment_powertranz.controllers.main import PowerTranzController

try:
    import pycountry
except ImportError:  # pragma: no cover - optional dependency
    pycountry = None

_logger = logging.getLogger(__name__)


def _powertranz_clean_text(value, max_length):
    """ Strip accents and characters refused by PowerTranz (`^[a-zA-Z0-9-' .]*$`). """
    value = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r"[^a-zA-Z0-9\-' .]", ' ', value)
    return re.sub(r'\s+', ' ', value).strip()[:max_length]


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # The HTML of the hosted page returned by `spi/sale`; served once by the redirect route.
    powertranz_redirect_data = fields.Text(
        string="PowerTranz Redirect Data", groups='base.group_system', copy=False, readonly=True,
    )
    powertranz_spi_token = fields.Char(
        string="PowerTranz SPI Token", groups='base.group_system', copy=False, readonly=True,
    )

    # === BUSINESS METHODS - PAYMENT FLOW === #

    def _powertranz_format_amount(self, amount):
        """ PowerTranz expects a JSON number in major units, rounded to the currency decimals. """
        return float_round(amount, precision_digits=self.currency_id.decimal_places)

    def _powertranz_get_currency_code(self):
        """ PowerTranz expects the ISO 4217 numeric code as a 3-digit string. """
        return str(self.currency_id.iso_numeric or '').zfill(3)

    def _powertranz_get_access_token(self):
        """ Same token as `payment_utils.generate_access_token`, without needing a request. """
        return hmac_tool(
            self.env(su=True), 'generate_access_token', f'{self.reference}|{self.provider_reference}'
        )

    def _powertranz_prepare_billing_address(self):
        """ Prepare the BillingAddress, following PowerTranz length and charset limits. """
        first_name, last_name = payment_utils.split_partner_name(self.partner_name or '')
        address = {
            'FirstName': _powertranz_clean_text(first_name, 30),
            'LastName': _powertranz_clean_text(last_name, 30),
            'Line1': _powertranz_clean_text(self.partner_address, 30),
            'City': _powertranz_clean_text(self.partner_city, 25),
            'PostalCode': re.sub(r'[^a-zA-Z0-9]', '', self.partner_zip or '')[:10],
            'EmailAddress': (self.partner_email or '')[:50],
            'PhoneNumber': re.sub(r'\D', '', self.partner_phone or '')[:20],
        }
        country_code = self.partner_country_id.code
        if pycountry and country_code:
            country = pycountry.countries.get(alpha_2=country_code)
            if country:
                address['CountryCode'] = country.numeric
        return {key: value for key, value in address.items() if value}

    def _get_specific_rendering_values(self, processing_values):
        """ Override of `payment` to create the PowerTranz hosted page session.

        PowerTranz returns the hosted page as an HTML document (`RedirectData`) instead of a URL,
        so it is stored on the transaction and served as a full page by a local route, which is
        where the redirect form points to.

        Note: self.ensure_one() from `_get_processing_values`.
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'powertranz':
            return res

        # Each attempt needs its own GUID; it is the key for every later call (refund, lookup).
        self.provider_reference = str(uuid.uuid4())
        base_url = self.provider_id.get_base_url()
        access_token = self._powertranz_get_access_token()
        return_url = urls.url_join(base_url, PowerTranzController._return_url) + '?' + urls.url_encode({
            'reference': self.reference, 'access_token': access_token,
        })
        use_3ds = self.provider_id.powertranz_use_3ds
        payload = {
            'TransactionIdentifier': self.provider_reference,
            'TotalAmount': self._powertranz_format_amount(self.amount),
            'CurrencyCode': self._powertranz_get_currency_code(),
            'ThreeDSecure': use_3ds,
            'OrderIdentifier': self.reference,
            'AddressMatch': False,
            'BillingAddress': self._powertranz_prepare_billing_address(),
            'ExtendedData': {
                'MerchantResponseUrl': return_url,
                'HostedPage': {
                    'PageSet': self.provider_id._powertranz_get_page_set(),
                    'PageName': (self.provider_id.powertranz_page_name or '').strip(),
                },
            },
        }
        if use_3ds:
            payload['ExtendedData']['ThreeDSecure'] = {
                'ChallengeWindowSize': const.CHALLENGE_WINDOW_SIZE_FULL_PAGE,
                'ChallengeIndicator': '01',
            }
        response = self.provider_id._powertranz_make_request('spi/sale', payload=payload)
        if response.get('IsoResponseCode') != const.SPI_PREPROCESSING_OK \
                or not response.get('RedirectData'):
            _logger.warning(
                "PowerTranz: could not start the payment of transaction %s: %s",
                self.reference, self._powertranz_get_error_message(response),
            )
            raise ValidationError("PowerTranz: " + _(
                "The payment could not be started: %s", self._powertranz_get_error_message(response)
            ))
        self.write({
            'powertranz_redirect_data': response['RedirectData'],
            'powertranz_spi_token': response.get('SpiToken'),
        })
        return {
            'api_url': urls.url_join(base_url, PowerTranzController._redirect_url),
            'reference': self.reference,
            'access_token': access_token,
        }

    def _powertranz_lock_for_update(self):
        """ Lock the transaction row so that concurrent callbacks are processed only once. """
        self.ensure_one()
        self.env.cr.execute(
            'SELECT id FROM payment_transaction WHERE id = %s FOR UPDATE', [self.id]
        )
        self.invalidate_recordset()

    def _powertranz_handle_hpp_callback(self, callback_data):
        """ Handle the data posted by the hosted page to the MerchantResponseUrl.

        The callback travels through the customer's browser and is not signed: it only tells
        whether the card data was collected and how 3DS went. No money moves until the payment is
        completed server-to-server with `spi/payment`, whose response is what confirms the
        transaction.

        :param dict callback_data: The decoded `Response` document posted by PowerTranz.
        :return: None
        """
        self.ensure_one()
        self._powertranz_lock_for_update()
        if self.state != 'draft':
            _logger.info("PowerTranz: transaction %s already processed, skipping.", self.reference)
            return
        posted_guid = callback_data.get('TransactionIdentifier')
        if posted_guid and posted_guid != self.provider_reference:
            raise ValidationError("PowerTranz: " + _(
                "The transaction identifier does not match the transaction %s.", self.reference
            ))

        refusal_reason = self._powertranz_get_hpp_refusal_reason(callback_data)
        if refusal_reason:
            self.powertranz_redirect_data = False
            self._handle_notification_data('powertranz', {
                'reference': self.reference,
                'Approved': False,
                'IsoResponseCode': callback_data.get('IsoResponseCode'),
                'ResponseMessage': refusal_reason,
                'TransactionIdentifier': self.provider_reference,
            })
            return

        spi_token = self.powertranz_spi_token or callback_data.get('SpiToken')
        try:
            payment_data = self.provider_id._powertranz_make_request(
                'spi/payment', spi_token=spi_token
            )
        except ValidationError:
            # An expired or already used token gives HTTP 400. The payment may have been completed
            # by a previous callback whose response was lost: check the gateway before failing.
            _logger.warning(
                "PowerTranz: payment completion failed for %s, checking the transaction status.",
                self.reference,
            )
            payment_data = self._powertranz_fetch_payment_status()
            if not payment_data:
                payment_data = {
                    'Approved': False,
                    'ResponseMessage': _("The payment could not be completed (session expired)."),
                    'TransactionIdentifier': self.provider_reference,
                }
        self.write({'powertranz_redirect_data': False, 'powertranz_spi_token': False})
        self._handle_notification_data('powertranz', dict(payment_data, reference=self.reference))

    def _powertranz_get_hpp_refusal_reason(self, callback_data):
        """ Decide, from the callback, whether the payment may be completed.

        :return: The reason to refuse the payment, or None if it can be completed.
        :rtype: str|None
        """
        iso_code = callback_data.get('IsoResponseCode')
        provider = self.provider_id
        if iso_code == const.HPP_DATA_COLLECTED:
            return None
        if iso_code == const.THREEDS_COMPLETE:
            threeds = (callback_data.get('RiskManagement') or {}).get('ThreeDSecure') or {}
            status = threeds.get('AuthenticationStatus')
            if status in const.THREEDS_AUTHENTICATED_STATUSES:
                return None
            if status == const.THREEDS_UNAVAILABLE_STATUS and provider.powertranz_allow_3ds_unavailable:
                return None
            return _(
                "The 3-D Secure authentication was not successful (status %s).", status or '?'
            )
        if iso_code in const.THREEDS_NOT_SUPPORTED:
            if provider.powertranz_allow_non_3ds_cards:
                return None
            return _("The card does not support 3-D Secure.")
        return callback_data.get('ResponseMessage') or _(
            "The hosted payment page returned the code %s.", iso_code or '?'
        )

    def _powertranz_fetch_payment_status(self):
        """ Fetch the sale from PowerTranz and normalize it like a `spi/payment` response.

        :return: The normalized payment data, or an empty dict if the sale is not found.
        :rtype: dict
        """
        self.ensure_one()
        try:
            data = self.provider_id._powertranz_make_request(
                f'transactions/{self.provider_reference}', method='GET'
            )
        except ValidationError:
            return {}
        if not isinstance(data, dict) or data.get('TransactionType') != const.TRANSACTION_TYPE_SALE:
            return {}
        iso_code = data.get('IsoResponseCode')
        return {
            'Approved': iso_code == const.APPROVED_ISO_CODE,
            'IsoResponseCode': iso_code,
            'ResponseMessage': data.get('ResponseMessage'),
            'TransactionIdentifier': data.get('TransactionIdentifier'),
            'TotalAmount': data.get('TotalAmount'),
            'CurrencyCode': data.get('CurrencyCode'),
            'OrderIdentifier': (data.get('OrderSummary') or {}).get('OrderIdentifier'),
            'AuthorizationCode': data.get('AuthorizationCode'),
            'RRN': data.get('Rrn'),
        }

    # === BUSINESS METHODS - REFUND FLOW === #

    def _send_refund_request(self, amount_to_refund=None):
        """ Override of `payment` to send a refund request to PowerTranz.

        Note: self.ensure_one()

        :param float amount_to_refund: The amount to refund.
        :return: The refund transaction created to process the refund request.
        :rtype: recordset of `payment.transaction`
        """
        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        if self.provider_code != 'powertranz':
            return refund_tx

        payload = {
            'Refund': True,
            'TransactionIdentifier': self.provider_reference,
            'TotalAmount': refund_tx._powertranz_format_amount(-refund_tx.amount),
            'CurrencyCode': refund_tx._powertranz_get_currency_code(),
            'OrderIdentifier': self.reference,
            'ExternalIdentifier': refund_tx.reference,
            'Source': {
                'CardPresent': False,
                'CardEmvFallback': False,
                'ManualEntry': False,
                'Debit': False,
                'Contactless': False,
                'CardPan': '',
                'MaskedPan': '',
            },
            'TerminalCode': '',
            'TerminalSerialNumber': '',
            'AddressMatch': False,
        }
        response = refund_tx.provider_id._powertranz_make_request('refund', payload=payload)
        refund_tx._handle_notification_data(
            'powertranz', dict(response, reference=refund_tx.reference)
        )
        return refund_tx

    # === BUSINESS METHODS - NOTIFICATION PROCESSING === #

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of `payment` to find the transaction based on PowerTranz data.

        The notification data always comes from a server-to-server response, enriched by this
        module with the Odoo `reference` of the transaction.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'powertranz' or len(tx) == 1:
            return tx

        reference = notification_data.get('reference')
        if not reference:
            raise ValidationError("PowerTranz: " + _("Received data with missing reference."))
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'powertranz')])
        if not tx:
            raise ValidationError("PowerTranz: " + _(
                "No transaction found matching reference %s.", reference
            ))
        return tx

    def _process_notification_data(self, notification_data):
        """ Override of `payment` to process the transaction based on PowerTranz data.

        Note: self.ensure_one()
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'powertranz':
            return

        if self.operation == 'refund':
            self._powertranz_process_refund_data(notification_data)
        else:
            self._powertranz_process_payment_data(notification_data)

    def _powertranz_process_payment_data(self, data):
        approved = data.get('Approved') and data.get('IsoResponseCode') == const.APPROVED_ISO_CODE
        if not approved:
            self._set_error("PowerTranz: " + _(
                "The payment was declined: %s", self._powertranz_get_error_message(data)
            ))
            return

        # The response is authentic (server-to-server) but make sure it is about this payment.
        mismatch = self._powertranz_get_mismatch(
            data, expected_guid=self.provider_reference, expected_amount=self.amount,
        )
        if data.get('OrderIdentifier') and data['OrderIdentifier'] != self.reference:
            mismatch = _("order identifier")
        if mismatch:
            _logger.error(
                "PowerTranz: %s mismatch on transaction %s: %s", mismatch, self.reference, data
            )
            self._set_error("PowerTranz: " + _(
                "The payment data does not match the transaction (%s).", mismatch
            ))
            return

        self._powertranz_update_payment_method(data.get('CardBrand'))
        self._set_done(state_message=self._powertranz_get_state_message(data))

    def _powertranz_process_refund_data(self, data):
        if data.get('TransactionIdentifier'):
            self.provider_reference = data['TransactionIdentifier']
        # Some endpoints answer Approved without an IsoResponseCode.
        iso_code = data.get('IsoResponseCode')
        approved = data.get('Approved') and iso_code in (const.APPROVED_ISO_CODE, None, '')
        if not approved:
            self._set_error("PowerTranz: " + _(
                "The refund was refused: %s", self._powertranz_get_error_message(data)
            ))
            return

        source_guid = self.source_transaction_id.provider_reference
        if data.get('OriginalTrxnIdentifier') and data['OriginalTrxnIdentifier'] != source_guid:
            mismatch = _("original transaction")
        else:
            mismatch = self._powertranz_get_mismatch(data, expected_amount=-self.amount)
        if mismatch:
            # The money was refunded but the data is unexpected: keep the tx open for a human.
            _logger.error(
                "PowerTranz: %s mismatch on refund %s: %s", mismatch, self.reference, data
            )
            self._set_pending(state_message="PowerTranz: " + _(
                "The refund was approved but its data does not match (%s). Please check it in "
                "the PowerTranz portal.", mismatch,
            ))
            return

        self._set_done(state_message=self._powertranz_get_state_message(data))
        # Create the outbound accounting payment right away instead of waiting for the cron.
        self.env.ref('payment.cron_post_process_payment_tx')._trigger()

    def _powertranz_get_mismatch(self, data, expected_amount, expected_guid=None):
        """ Return the name of the first field of `data` that does not match, if any. """
        if expected_guid and data.get('TransactionIdentifier') != expected_guid:
            return _("transaction identifier")
        if data.get('CurrencyCode') and str(data['CurrencyCode']).zfill(3) \
                != self._powertranz_get_currency_code():
            return _("currency")
        if data.get('TotalAmount') is None or float_compare(
            float(data['TotalAmount']), expected_amount,
            precision_digits=self.currency_id.decimal_places,
        ) != 0:
            return _("amount")
        return None

    def _powertranz_update_payment_method(self, card_brand):
        """ Set the card brand as payment method when PowerTranz returns it. """
        if not card_brand:
            return
        payment_method = self.env['payment.method']._get_from_code(
            const.PAYMENT_METHODS_MAPPING.get(card_brand.lower(), card_brand.lower())
        )
        if payment_method:
            self.payment_method_id = payment_method

    @api.model
    def _powertranz_get_error_message(self, data):
        """ Build a readable message from a PowerTranz response. """
        if not isinstance(data, dict):
            return _("Unknown error")
        errors = ', '.join(
            f"{error.get('Message')} ({error.get('Code')})" for error in data.get('Errors') or []
        )
        message = data.get('ResponseMessage') or _("Unknown error")
        if data.get('IsoResponseCode'):
            message = f"{message} [{data['IsoResponseCode']}]"
        return f"{message} - {errors}" if errors else message

    @api.model
    def _powertranz_get_state_message(self, data):
        parts = []
        if data.get('AuthorizationCode'):
            parts.append(_("Authorization code: %s", data['AuthorizationCode']))
        if data.get('RRN'):
            parts.append(_("RRN: %s", data['RRN']))
        return ' / '.join(parts) or None
