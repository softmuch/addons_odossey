# Part of Odossey. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.odossey_payment_powertranz.tests.common import MAKE_REQUEST, PowerTranzCommon

LOGGERS = (
    'odoo.addons.odossey_payment_powertranz.models.payment_transaction',
    'odoo.addons.payment.models.payment_transaction',
)


@tagged('post_install', '-at_install')
class TestRefundFlows(PowerTranzCommon):

    def _get_refund_tx(self, source_tx):
        return self.env['payment.transaction'].search([('source_transaction_id', '=', source_tx.id)])

    def test_partial_refund_request_and_processing(self):
        source_tx = self._create_transaction('redirect', state='done', provider_reference=self.guid)
        with patch(MAKE_REQUEST, return_value=self.refund_approved) as mock:
            refund_tx = source_tx._send_refund_request(amount_to_refund=50.0)

        endpoint = mock.call_args.args[0]
        payload = mock.call_args.kwargs['payload']
        self.assertEqual(endpoint, 'refund')
        self.assertIs(payload['Refund'], True)
        self.assertEqual(payload['TransactionIdentifier'], self.guid)
        self.assertEqual(payload['TotalAmount'], 50.0)
        self.assertEqual(payload['CurrencyCode'], '840')
        self.assertEqual(payload['OrderIdentifier'], source_tx.reference)
        self.assertEqual(payload['ExternalIdentifier'], refund_tx.reference)
        self.assertIn('Source', payload)

        self.assertEqual(refund_tx, self._get_refund_tx(source_tx))
        self.assertEqual(refund_tx.operation, 'refund')
        self.assertEqual(refund_tx.amount, -50.0)
        self.assertEqual(refund_tx.state, 'done')
        self.assertEqual(refund_tx.provider_reference, self.refund_guid)
        self.assertEqual(source_tx.provider_reference, self.guid)

    def test_full_refund(self):
        source_tx = self._create_transaction('redirect', state='done', provider_reference=self.guid)
        response = dict(self.refund_approved, TotalAmount=self.amount)
        with patch(MAKE_REQUEST, return_value=response) as mock:
            refund_tx = source_tx._send_refund_request()
        self.assertEqual(mock.call_args.kwargs['payload']['TotalAmount'], self.amount)
        self.assertEqual(refund_tx.amount, -self.amount)
        self.assertEqual(refund_tx.state, 'done')

    def test_refund_approved_without_iso_code(self):
        source_tx = self._create_transaction('redirect', state='done', provider_reference=self.guid)
        response = dict(self.refund_approved)
        response.pop('IsoResponseCode')
        with patch(MAKE_REQUEST, return_value=response):
            refund_tx = source_tx._send_refund_request(amount_to_refund=50.0)
        self.assertEqual(refund_tx.state, 'done')

    @mute_logger(*LOGGERS)
    def test_refused_refund_sets_error(self):
        source_tx = self._create_transaction('redirect', state='done', provider_reference=self.guid)
        response = dict(
            self.refund_approved, Approved=False, IsoResponseCode='12',
            ResponseMessage='Invalid transaction',
            Errors=[{'Code': '343', 'Message': 'Invalid merchant'}],
        )
        with patch(MAKE_REQUEST, return_value=response):
            refund_tx = source_tx._send_refund_request(amount_to_refund=50.0)
        self.assertEqual(refund_tx.state, 'error')
        self.assertIn('Invalid merchant', refund_tx.state_message)

    @mute_logger(*LOGGERS)
    def test_refund_with_mismatching_data_stays_pending(self):
        for index, values in enumerate((
            {'TotalAmount': 49.0}, {'OriginalTrxnIdentifier': 'other-guid'},
        )):
            source_tx = self._create_transaction(
                'redirect', reference=f'S00050-{index}', state='done', provider_reference=self.guid,
            )
            response = dict(self.refund_approved, **values)
            with patch(MAKE_REQUEST, return_value=response):
                refund_tx = source_tx._send_refund_request(amount_to_refund=50.0)
            self.assertEqual(refund_tx.state, 'pending')
            self.assertIn('does not match', refund_tx.state_message)


@tagged('post_install', '-at_install')
class TestRefundAccounting(PowerTranzCommon):
    """ Full backend flow: payment -> account.payment -> Refund wizard -> outbound payment. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.enable_post_process_patcher = False

    def test_refund_wizard_creates_outbound_payment(self):
        self._skip_if_account_payment_is_not_installed()
        if not self.provider.journal_id:
            self.skipTest("No bank journal available for the provider")

        source_tx = self._create_transaction('redirect', state='done', provider_reference=self.guid)
        source_tx._post_process()
        payment = source_tx.payment_id
        self.assertTrue(payment, "The confirmed transaction must create an accounting payment")
        self.assertEqual(payment.amount_available_for_refund, self.amount)

        action = payment.action_refund_wizard()
        wizard = self.env[action['res_model']].with_context(
            active_model='account.payment', active_id=payment.id,
        ).create({
            'amount_to_refund': 50.0,
        })
        self.assertEqual(wizard.support_refund, 'partial')
        with patch(MAKE_REQUEST, return_value=self.refund_approved):
            wizard.action_refund()

        refund_tx = self.env['payment.transaction'].search(
            [('source_transaction_id', '=', source_tx.id)]
        )
        self.assertEqual(refund_tx.state, 'done')
        refund_tx._post_process()
        refund_payment = refund_tx.payment_id
        self.assertEqual(refund_payment.payment_type, 'outbound')
        self.assertEqual(refund_payment.amount, 50.0)
        self.assertEqual(refund_payment.source_payment_id, payment)
        payment.invalidate_recordset()
        self.assertEqual(payment.amount_available_for_refund, self.amount - 50.0)
