# Part of Odossey. See LICENSE file for full copyright and licensing details.

import json
import logging
import pprint

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.payment import utils as payment_utils

_logger = logging.getLogger(__name__)


class PowerTranzController(http.Controller):
    _redirect_url = '/payment/powertranz/redirect'
    _return_url = '/payment/powertranz/return'

    @staticmethod
    def _get_tx_from_access_token(reference, access_token):
        """ Return the PowerTranz transaction matching the reference if the access token is valid.

        :raise Forbidden: If the transaction is not found or the access token is invalid.
        """
        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference or ''), ('provider_code', '=', 'powertranz'),
        ], limit=1)
        if not tx_sudo or not tx_sudo.provider_reference or not payment_utils.check_access_token(
            access_token, tx_sudo.reference, tx_sudo.provider_reference
        ):
            _logger.warning("PowerTranz: invalid access token for reference %s", reference)
            raise Forbidden()
        return tx_sudo

    @http.route(_redirect_url, type='http', auth='public', methods=['GET'], csrf=False, sitemap=False)
    def powertranz_redirect_to_hosted_page(self, reference=None, access_token=None, **_kwargs):
        """ Serve the hosted payment page HTML returned by PowerTranz as a full page.

        PowerTranz gives a self-submitting HTML document instead of a URL; serving it as a top-level
        document lets its scripts run, as the payment form only keeps the first <form> it receives.
        """
        tx_sudo = self._get_tx_from_access_token(reference, access_token)
        if tx_sudo.state != 'draft' or not tx_sudo.powertranz_redirect_data:
            return request.redirect('/payment/status')
        return request.make_response(tx_sudo.powertranz_redirect_data, headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store'),
        ])

    @http.route(
        _return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False,
        save_session=False,
    )
    def powertranz_return_from_hosted_page(self, reference=None, access_token=None, **data):
        """ Process the result posted by the hosted page (MerchantResponseUrl).

        PowerTranz posts a form with the fields `Response` (a JSON document), `TransactionIdentifier`
        and `SpiToken`. The reference and the access token are in the query string we gave it.

        The route is called from a cross-site POST, so the session cookie may be missing: the
        session is not saved to avoid replacing the customer's session (see payment_aps), and the
        redirection to the status page brings the original session back.
        """
        tx_sudo = self._get_tx_from_access_token(reference, access_token)
        _logger.info(
            "PowerTranz: return data for %s:\n%s", tx_sudo.reference,
            pprint.pformat({k: v for k, v in data.items() if k.lower() != 'spitoken'}),
        )
        try:
            callback_data = self._parse_callback_data(data)
            tx_sudo._powertranz_handle_hpp_callback(callback_data)
        except ValidationError:
            _logger.exception("PowerTranz: unable to handle the return data of %s", tx_sudo.reference)
        return request.redirect('/payment/status')

    @staticmethod
    def _parse_callback_data(data):
        """ Decode the posted `Response` JSON and complete it with the top-level fields. """
        raw_response = data.get('Response') or data.get('response')
        callback_data = {}
        if raw_response:
            try:
                callback_data = json.loads(raw_response)
            except ValueError:
                raise ValidationError("PowerTranz: invalid Response data.")
        if not isinstance(callback_data, dict):
            raise ValidationError("PowerTranz: invalid Response data.")
        for key in ('SpiToken', 'TransactionIdentifier'):
            value = data.get(key) or data.get(key[0].lower() + key[1:]) or data.get(key.lower())
            if value and not callback_data.get(key):
                callback_data[key] = value
        return callback_data
