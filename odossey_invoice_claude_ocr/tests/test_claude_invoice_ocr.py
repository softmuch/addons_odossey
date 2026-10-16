# -*- coding: utf-8 -*-
import base64
import json
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.odossey_invoice_claude_ocr.models import claude_client

EXTRACT_PATH = 'odoo.addons.odossey_invoice_claude_ocr.models.claude_client.extract_invoice'
FAKE_PDF = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF'


def _party(**values):
    party = dict.fromkeys(('name', 'vat', 'street', 'city', 'zip', 'country_code', 'email', 'phone', 'iban'), '')
    party.update(values)
    return party


@tagged('post_install', '-at_install')
class TestClaudeInvoiceOcr(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a.vat = 'BE0477472701'
        cls.product_a.default_code = 'PROD-A'
        cls.rate = cls.tax_purchase_a.amount

    def _result(self, **overrides):
        result = {
            'document_type': 'invoice',
            'supplier': _party(name='Partner A Ltd', vat='BE0477472701', iban='BE68 5390 0754 7034'),
            'customer': _party(name=self.env.company.name),
            'invoice_number': 'INV/2026/0042',
            'invoice_date': '2026-10-01',
            'due_date': '2026-10-31',
            'currency': self.env.company.currency_id.name,
            'payment_reference': '+++123/4567/89012+++',
            'purchase_order': '',
            'amount_untaxed': 300.0,
            'amount_tax': 300.0 * self.rate / 100,
            'amount_total': 300.0 * (1 + self.rate / 100),
            'lines': [
                {'description': 'Product A', 'product_code': 'PROD-A', 'quantity': 2.0, 'unit_price': 100.0,
                 'discount_pct': 0.0, 'tax_rate_pct': self.rate, 'subtotal': 200.0},
                {'description': 'Consulting services', 'product_code': '', 'quantity': 1.0, 'unit_price': 100.0,
                 'discount_pct': 0.0, 'tax_rate_pct': self.rate, 'subtotal': 100.0},
            ],
            'unmapped': [
                {'label': 'Delivery note', 'value': 'DN-778'},
                {'label': 'Order number', 'value': 'PO00012'},
                {'label': 'Bank', 'value': 'ING Belgium'},
            ],
            'confidence': [{'field': 'invoice_number', 'level': 'high'}, {'field': 'currency', 'level': 'low'}],
        }
        result.update(overrides)
        return result

    def _new_wizard(self, result, **vals):
        wizard = self.env['claude.invoice.wizard'].create({
            'file': base64.b64encode(FAKE_PDF).decode(),
            'file_name': 'bill.pdf',
            'journal_id': self.company_data['default_journal_purchase'].id,
            **vals,
        })
        with patch(EXTRACT_PATH, return_value=result) as mocked:
            action = wizard.action_read()
        return wizard, action, mocked

    # -------------------------------------------------------------------------
    # Claude client
    # -------------------------------------------------------------------------

    def test_client_build_payload(self):
        payload = claude_client.build_payload(FAKE_PDF, 'application/pdf', model='claude-haiku-5-5')
        content = payload['messages'][0]['content']
        self.assertEqual(content[0]['type'], 'document')
        self.assertEqual(base64.b64decode(content[0]['source']['data']), FAKE_PDF)
        self.assertEqual(payload['output_config']['format']['type'], 'json_schema')
        self.assertIn('unmapped', payload['output_config']['format']['schema']['required'])
        image = claude_client.build_payload(b'img', 'image/png')
        self.assertEqual(image['messages'][0]['content'][0]['type'], 'image')
        with self.assertRaises(claude_client.ClaudeError):
            claude_client.build_payload(b'x', 'application/zip')

    def test_client_parse_response(self):
        body = {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps({'a': 1})}]}
        self.assertEqual(claude_client.parse_response(body), {'a': 1})
        with self.assertRaises(claude_client.ClaudeError):
            claude_client.parse_response({'stop_reason': 'max_tokens', 'content': []})
        with self.assertRaises(claude_client.ClaudeError):
            claude_client.parse_response({'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '{oops'}]})

    def test_client_http_retry_and_errors(self):
        overloaded = MagicMock(status_code=529, headers={'retry-after': '1'})
        overloaded.json.return_value = {'error': {'message': 'Overloaded'}}
        ok = MagicMock(status_code=200, headers={'request-id': 'req_1'})
        ok.json.return_value = {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '{"x": 2}'}]}
        session = MagicMock()
        session.post.side_effect = [overloaded, ok]
        with patch.object(claude_client.time, 'sleep'):
            self.assertEqual(claude_client.extract_invoice('key', FAKE_PDF, 'application/pdf', session=session), {'x': 2})
        headers = session.post.call_args.kwargs['headers']
        self.assertEqual(headers['x-api-key'], 'key')
        self.assertEqual(headers['anthropic-version'], claude_client.API_VERSION)

        unauthorized = MagicMock(status_code=401, headers={})
        unauthorized.json.return_value = {'error': {'message': 'invalid x-api-key'}}
        session.post.side_effect = [unauthorized]
        with self.assertRaisesRegex(claude_client.ClaudeError, 'invalid x-api-key'):
            claude_client.extract_invoice('bad', FAKE_PDF, 'application/pdf', session=session)
        with self.assertRaisesRegex(claude_client.ClaudeError, 'API key'):
            claude_client.extract_invoice('', FAKE_PDF, 'application/pdf', session=session)

    # -------------------------------------------------------------------------
    # Wizard
    # -------------------------------------------------------------------------

    def test_wizard_read_maps_fields(self):
        self.env['ir.config_parameter'].sudo().set_str('odossey_invoice_claude_ocr.api_key', 'sk-test')
        wizard, action, mocked = self._new_wizard(self._result())
        self.assertEqual(mocked.call_args.args[0], 'sk-test')
        self.assertEqual(mocked.call_args.args[2], 'application/pdf')
        self.assertEqual(action['res_id'], wizard.id)
        self.assertEqual(action['target'], 'new')
        self.assertRecordValues(wizard, [{
            'state': 'review',
            'is_pdf': True,
            'partner_id': self.partner_a.id,
            'ref': 'INV/2026/0042',
            'payment_reference': '+++123/4567/89012+++',
            'currency_id': self.env.company.currency_id.id,
            'amount_untaxed_read': 300.0,
            'amount_untaxed_lines': 300.0,
            'totals_mismatch': False,
            'low_confidence': 'Currency',
            'unmapped_pending_count': 3,
        }])
        self.assertEqual(str(wizard.invoice_date), '2026-10-01')
        self.assertEqual(wizard.line_ids[0].product_id, self.product_a)
        self.assertEqual(wizard.line_ids[0].tax_ids, self.tax_purchase_a)
        self.assertTrue(wizard.line_ids[1].tax_ids)
        self.assertEqual(wizard.unmapped_ids.mapped('label'), ['Delivery note', 'Order number', 'Bank'])

    def test_wizard_confirm_requires_placing_all_data(self):
        wizard, _action, _mocked = self._new_wizard(self._result())
        with self.assertRaisesRegex(UserError, 'Delivery note'):
            wizard.action_confirm()

    def test_wizard_place_unmapped_and_create_bill(self):
        result = self._result()
        result['unmapped'].append({'label': 'Shipping costs', 'value': '12,50'})
        wizard, _action, _mocked = self._new_wizard(result)

        with Form(wizard) as wizard_form:
            targets = ['narration', 'invoice_origin', 'discard', 'line']
            for index, target in enumerate(targets):
                with wizard_form.unmapped_ids.edit(index) as row:
                    row.target = target
            # the onchange places each value in the chosen field of the mask immediately
            self.assertEqual(wizard_form.invoice_origin, 'PO00012')
            self.assertEqual(wizard_form.narration, 'Delivery note: DN-778')
            self.assertEqual(len(wizard_form.line_ids), 3)

        action = wizard.action_confirm()
        move = self.env['account.move'].browse(action['res_id'])
        self.assertRecordValues(move, [{
            'state': 'draft',
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'ref': 'INV/2026/0042',
            'invoice_origin': 'PO00012',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'amount_untaxed': 312.5,
        }])
        self.assertIn('DN-778', str(move.narration))
        self.assertEqual(str(move.invoice_date), '2026-10-01')
        self.assertEqual(move.partner_bank_id.sanitized_account_number, 'BE68539007547034')
        self.assertRecordValues(move.invoice_line_ids.sorted('sequence'), [
            {'name': 'Product A', 'product_id': self.product_a.id, 'quantity': 2.0, 'price_unit': 100.0,
             'tax_ids': self.tax_purchase_a.ids},
            {'name': 'Consulting services', 'product_id': False, 'quantity': 1.0, 'price_unit': 100.0,
             'tax_ids': move.invoice_line_ids.sorted('sequence')[1].tax_ids.ids},
            {'name': 'Shipping costs', 'product_id': False, 'quantity': 1.0, 'price_unit': 12.5,
             'tax_ids': move.invoice_line_ids.sorted('sequence')[2].tax_ids.ids},
        ])
        self.assertEqual(move.message_main_attachment_id.name, 'bill.pdf')
        self.assertEqual(move.message_main_attachment_id.raw.content, FAKE_PDF)

    def test_wizard_invalid_date_placement(self):
        result = self._result(unmapped=[{'label': 'Delivery date', 'value': 'next monday-ish'}])
        wizard, _action, _mocked = self._new_wizard(result)
        wizard.unmapped_ids.target = 'invoice_date_due'
        with self.assertRaisesRegex(UserError, 'not a valid date'):
            wizard.action_confirm()
        wizard.unmapped_ids.write({'target': 'invoice_date_due', 'value': '15/11/2026'})
        move = self.env['account.move'].browse(wizard.action_confirm()['res_id'])
        self.assertEqual(str(move.invoice_date_due), '2026-11-15')

    def test_wizard_unknown_vendor_credit_note(self):
        result = self._result(
            document_type='credit_note',
            supplier=_party(name='Brand New Supplier SRL', email='ap@brandnew.example', country_code='IT'),
            currency='ZZZ',
            unmapped=[],
            lines=[{'description': 'Refund', 'product_code': '', 'quantity': 1.0, 'unit_price': -50.0,
                    'discount_pct': 0.0, 'tax_rate_pct': None, 'subtotal': -50.0}],
            amount_untaxed=-50.0, amount_tax=0.0, amount_total=-50.0,
        )
        wizard, _action, _mocked = self._new_wizard(result)
        self.assertFalse(wizard.partner_id)
        self.assertEqual(wizard.move_type, 'in_refund')
        self.assertEqual(wizard.line_ids.price_unit, 50.0)
        # unknown currency becomes a datum to place
        self.assertEqual(wizard.unmapped_ids.value, 'ZZZ')
        wizard.unmapped_ids.target = 'narration'
        move = self.env['account.move'].browse(wizard.action_confirm()['res_id'])
        self.assertEqual(move.move_type, 'in_refund')
        self.assertEqual(move.partner_id.name, 'Brand New Supplier SRL')
        self.assertEqual(move.partner_id.email, 'ap@brandnew.example')
        self.assertEqual(move.partner_id.country_id.code, 'IT')
        self.assertEqual(move.amount_untaxed, 50.0)

    def test_digitize_existing_draft_bill(self):
        bill = self.init_invoice('in_invoice', products=self.product_b)
        attachment = self.env['ir.attachment'].create({
            'name': 'scan.pdf', 'raw': FAKE_PDF, 'res_model': 'account.move', 'res_id': bill.id,
        })
        with patch(EXTRACT_PATH, return_value=self._result(unmapped=[])):
            action = bill.action_claude_digitize()
        wizard = self.env['claude.invoice.wizard'].browse(action['res_id'])
        self.assertRecordValues(wizard, [{'move_id': bill.id, 'attachment_id': attachment.id,
                                          'state': 'review', 'has_existing_lines': True}])
        wizard.action_confirm()
        self.assertEqual(bill.state, 'draft')
        self.assertEqual(bill.ref, 'INV/2026/0042')
        self.assertEqual(bill.invoice_line_ids.mapped('name'), ['Product A', 'Consulting services'])
        self.assertEqual(len(self.env['ir.attachment'].search([('res_model', '=', 'account.move'),
                                                               ('res_id', '=', bill.id)])), 1)

    def test_digitize_requires_draft_bill_with_document(self):
        bill = self.init_invoice('in_invoice', products=self.product_a)
        with self.assertRaisesRegex(UserError, 'Attach the invoice document'):
            bill.action_claude_digitize()
        invoice = self.init_invoice('out_invoice', products=self.product_a)
        with self.assertRaises(UserError):
            invoice.action_claude_digitize()

    def test_claude_error_is_user_error(self):
        wizard = self.env['claude.invoice.wizard'].create({
            'file': base64.b64encode(FAKE_PDF).decode(), 'file_name': 'bill.pdf',
        })
        with patch(EXTRACT_PATH, side_effect=claude_client.ClaudeError('Claude API error 401: invalid x-api-key')):
            with self.assertRaisesRegex(UserError, 'invalid x-api-key'):
                wizard.action_read()
