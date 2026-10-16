# Part of Odossey. See LICENSE file for full copyright and licensing details.

import json
import logging
import pprint

import requests

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.odossey_payment_powertranz import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('powertranz', "PowerTranz")], ondelete={'powertranz': 'set default'}
    )
    powertranz_merchant_id = fields.Char(
        string="PowerTranz ID",
        help="The PowerTranz ID (merchant ID) given by PowerTranz or the acquiring bank.",
        required_if_provider='powertranz',
        groups='base.group_system',
    )
    powertranz_password = fields.Char(
        string="PowerTranz Password",
        help="The processing password given by PowerTranz or the acquiring bank.",
        required_if_provider='powertranz',
        groups='base.group_system',
    )
    powertranz_gateway_key = fields.Char(
        string="Gateway Key",
        help="Only fill it if PowerTranz explicitly gave you a gateway key.",
        groups='base.group_system',
    )
    powertranz_page_set = fields.Char(
        string="Hosted Page Set",
        help="The Page Set of the hosted payment page created in the PowerTranz merchant portal. "
             "The 'PTZ/' prefix is added automatically.",
        required_if_provider='powertranz',
    )
    powertranz_page_name = fields.Char(
        string="Hosted Page Name",
        help="The Page Name of the hosted payment page created in the PowerTranz merchant portal.",
        required_if_provider='powertranz',
    )
    powertranz_api_url = fields.Char(
        string="Production API URL",
        help="Leave empty to use the default production API (https://gateway.ptranz.com/api/). "
             "Only change it if the bank gives you another host.",
        groups='base.group_system',
    )
    powertranz_use_3ds = fields.Boolean(
        string="3-D Secure",
        help="Authenticate the cardholder with 3-D Secure on the hosted page (recommended).",
        default=True,
    )
    powertranz_allow_non_3ds_cards = fields.Boolean(
        string="Accept cards without 3-D Secure",
        help="Complete the payment when the card is not enrolled in 3-D Secure. "
             "There is no liability shift for these payments.",
        default=True,
    )
    powertranz_allow_3ds_unavailable = fields.Boolean(
        string="Accept when 3-D Secure is unavailable",
        help="Complete the payment when the 3-D Secure authentication could not be performed "
             "(status U, technical problem). There is no liability shift for these payments.",
        default=False,
    )

    # === COMPUTE METHODS === #

    def _compute_feature_support_fields(self):
        """ Override of `payment` to enable additional features. """
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'powertranz').update({
            'support_refund': 'partial',
        })

    # === BUSINESS METHODS === #

    def _get_supported_currencies(self):
        """ Override of `payment` to return the supported currencies. """
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'powertranz':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'powertranz':
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _powertranz_get_api_url(self):
        """ Return the API root of the provider's environment, with a trailing slash. """
        self.ensure_one()
        if self.state == 'enabled':
            url = self.powertranz_api_url or const.API_URLS['enabled']
        else:
            url = const.API_URLS['test']
        return url.rstrip('/') + '/'

    def _powertranz_get_page_set(self):
        """ Return the Page Set with the mandatory 'PTZ/' prefix. """
        self.ensure_one()
        page_set = (self.powertranz_page_set or '').strip()
        if page_set and not page_set.upper().startswith('PTZ/'):
            page_set = f'PTZ/{page_set}'
        return page_set

    def _powertranz_make_request(self, endpoint, payload=None, method='POST', spi_token=None):
        """ Make a request to the PowerTranz API.

        PowerTranz answers business errors (declines, validation errors) with HTTP 200 and
        `Approved: false`, so those are returned as data. HTTP errors (400 with an empty body for
        an invalid or expired SPI token, 401, 415...) and connection errors raise.

        :param str endpoint: The endpoint to reach, relative to the API root.
        :param dict payload: The JSON payload of the request.
        :param str method: The HTTP method.
        :param str spi_token: The SPI token to send as a JSON string body (`spi/payment`).
        :return: The JSON-decoded response content.
        :rtype: dict
        :raise ValidationError: If an HTTP error occurs or the response is not JSON.
        """
        self.ensure_one()
        url = self._powertranz_get_api_url() + endpoint.lstrip('/')
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'PowerTranz-PowerTranzId': self.powertranz_merchant_id or '',
            'PowerTranz-PowerTranzPassword': self.powertranz_password or '',
        }
        if self.powertranz_gateway_key:
            headers['PowerTranz-GatewayKey'] = self.powertranz_gateway_key
        # The body of spi/payment is the token itself as a JSON string literal (with the quotes).
        if spi_token is not None:
            data = json.dumps(spi_token)
        elif payload is not None:
            data = json.dumps(payload)
        else:
            data = None
        _logger.info("PowerTranz: sending %s request to %s", method, url)
        try:
            response = requests.request(method, url, data=data, headers=headers, timeout=60)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            _logger.exception(
                "PowerTranz: invalid API request at %s (HTTP %s): %s",
                url, response.status_code, response.text[:500],
            )
            raise ValidationError("PowerTranz: " + _(
                "The communication with the API failed (HTTP %(status)s).",
                status=response.status_code,
            ))
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.exception("PowerTranz: unable to reach endpoint at %s", url)
            raise ValidationError(
                "PowerTranz: " + _("Could not establish the connection to the API.")
            )
        try:
            response_content = response.json()
        except ValueError:
            _logger.exception("PowerTranz: invalid JSON response from %s: %s", url, response.text[:500])
            raise ValidationError("PowerTranz: " + _("The API returned an invalid response."))
        _logger.info(
            "PowerTranz: response of %s:\n%s", endpoint, pprint.pformat(
                {k: v for k, v in response_content.items() if k not in ('RedirectData', 'SpiToken')}
                if isinstance(response_content, dict) else response_content
            ),
        )
        return response_content
