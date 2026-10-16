# -*- coding: utf-8 -*-
# Copyright (C) 2021-Today: Part of Odossey.
# @author:  Part of Odossey.
import logging
import os

from dateutil import parser as date_parser

from odoo import api, fields, models, Command
from odoo.addons.base.models.res_partner_bank import sanitize_account_number
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import float_compare, float_is_zero
from odoo.tools.mimetypes import guess_mimetype

from ..models import claude_client

_logger = logging.getLogger(__name__)

# Wizard char fields an unmapped datum can be moved to.
CHAR_TARGETS = (
    'ref', 'payment_reference', 'invoice_origin', 'iban',
    'supplier_name', 'supplier_vat', 'supplier_street', 'supplier_email', 'supplier_phone',
)
DATE_TARGETS = ('invoice_date', 'invoice_date_due')

TARGET_SELECTION = [
    ('ref', "Bill Reference"),
    ('payment_reference', "Payment Reference"),
    ('invoice_origin', "Source Document / PO"),
    ('invoice_date', "Bill Date"),
    ('invoice_date_due', "Due Date"),
    ('supplier_name', "Vendor Name"),
    ('supplier_vat', "Vendor Tax ID"),
    ('supplier_street', "Vendor Address"),
    ('supplier_email', "Vendor Email"),
    ('supplier_phone', "Vendor Phone"),
    ('iban', "Vendor Bank Account"),
    ('narration', "Terms and Conditions / Notes"),
    ('line', "New Invoice Line"),
    ('discard', "Discard"),
]

CONFIDENCE_FIELDS = {
    'supplier.vat': "Vendor Tax ID",
    'invoice_number': "Bill Reference",
    'invoice_date': "Bill Date",
    'currency': "Currency",
    'amount_total': "Total",
}


def _to_float(value):
    if isinstance(value, (int, float)):
        return float(value)
    text = (value or '').strip().replace(' ', '')
    for symbol in ('€', '$', '£', '%'):
        text = text.replace(symbol, '')
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.') if text.rfind(',') > text.rfind('.') else text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '.')
    return float(text)


def _to_date(value):
    """Parse an ISO date or a printed date (day first) into a date, None if impossible."""
    value = (value or '').strip()
    if not value:
        return None
    try:
        return fields.Date.to_date(value)
    except ValueError:
        pass
    try:
        return date_parser.parse(value, dayfirst=True).date()
    except (ValueError, OverflowError):
        return None


class ClaudeInvoiceWizard(models.TransientModel):
    _name = 'claude.invoice.wizard'
    _description = "Invoice Digitization with Claude"

    state = fields.Selection([('upload', "Upload"), ('review', "Review")], default='upload', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    move_id = fields.Many2one('account.move', string="Vendor Bill", readonly=True)
    journal_id = fields.Many2one(
        'account.journal', string="Journal",
        domain="[('type', '=', 'purchase'), ('company_id', 'parent_of', company_id)]",
        default=lambda self: self._default_journal_id(),
    )
    move_type = fields.Selection(
        [('in_invoice', "Vendor Bill"), ('in_refund', "Vendor Credit Note")],
        string="Type", default='in_invoice', required=True,
    )

    # Document
    attachment_id = fields.Many2one('ir.attachment', readonly=True)
    file = fields.Binary(string="Document", attachment=False)
    file_name = fields.Char()
    mimetype = fields.Char(compute='_compute_mimetype', store=True)
    is_pdf = fields.Boolean(compute='_compute_mimetype', store=True)
    file_pdf = fields.Binary(related='file', string="PDF Preview")
    file_image = fields.Binary(related='file', string="Image Preview")

    # Extraction metadata
    claude_model = fields.Char(readonly=True)
    raw_result = fields.Json(readonly=True)
    low_confidence = fields.Char(string="Low confidence", readonly=True)

    # Vendor
    partner_id = fields.Many2one(
        'res.partner', string="Vendor",
        domain="[('company_id', 'in', (False, company_id))]",
    )
    create_partner = fields.Boolean(
        string="Create vendor", default=True,
        help="Create the vendor from the data read when no existing contact is selected.",
    )
    supplier_name = fields.Char(string="Vendor Name (read)")
    supplier_vat = fields.Char(string="Vendor Tax ID (read)")
    supplier_street = fields.Char(string="Vendor Address (read)")
    supplier_city = fields.Char(string="City (read)")
    supplier_zip = fields.Char(string="ZIP (read)")
    supplier_country_id = fields.Many2one('res.country', string="Country (read)")
    supplier_email = fields.Char(string="Vendor Email (read)")
    supplier_phone = fields.Char(string="Vendor Phone (read)")
    iban = fields.Char(string="Vendor Bank Account")

    # Bill header
    ref = fields.Char(string="Bill Reference")
    invoice_date = fields.Date(string="Bill Date")
    invoice_date_due = fields.Date(string="Due Date")
    currency_id = fields.Many2one(
        'res.currency', string="Currency", default=lambda self: self.env.company.currency_id,
    )
    payment_reference = fields.Char(string="Payment Reference")
    invoice_origin = fields.Char(string="Source Document / PO")
    narration = fields.Text(string="Terms and Conditions / Notes")

    # Totals printed on the document
    amount_untaxed_read = fields.Float(string="Untaxed Amount (read)", digits='Account')
    amount_tax_read = fields.Float(string="Taxes (read)", digits='Account')
    amount_total_read = fields.Float(string="Total (read)", digits='Account')
    amount_untaxed_lines = fields.Float(
        string="Untaxed Amount (lines)", digits='Account', compute='_compute_amount_untaxed_lines',
    )
    totals_mismatch = fields.Boolean(compute='_compute_amount_untaxed_lines')

    line_ids = fields.One2many('claude.invoice.wizard.line', 'wizard_id', string="Invoice Lines")
    unmapped_ids = fields.One2many('claude.invoice.wizard.unmapped', 'wizard_id', string="Data to place")
    unmapped_pending_count = fields.Integer(compute='_compute_unmapped_pending_count')
    has_existing_lines = fields.Boolean(compute='_compute_has_existing_lines')

    # -------------------------------------------------------------------------
    # DEFAULTS / COMPUTES
    # -------------------------------------------------------------------------

    @api.model
    def _default_journal_id(self):
        return self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.env.company),
            ('type', '=', 'purchase'),
        ], limit=1)

    @api.depends('file', 'file_name', 'attachment_id')
    def _compute_mimetype(self):
        for wizard in self:
            mimetype = wizard.attachment_id.mimetype
            if not mimetype and wizard.file:
                mimetype = guess_mimetype(wizard.file.content)
            wizard.mimetype = mimetype
            wizard.is_pdf = mimetype == 'application/pdf'

    @api.depends('line_ids.price_subtotal', 'amount_untaxed_read')
    def _compute_amount_untaxed_lines(self):
        for wizard in self:
            wizard.amount_untaxed_lines = sum(wizard.line_ids.mapped('price_subtotal'))
            wizard.totals_mismatch = bool(wizard.amount_untaxed_read) and float_compare(
                wizard.amount_untaxed_lines, wizard.amount_untaxed_read, precision_digits=2) != 0

    @api.depends('unmapped_ids.target')
    def _compute_unmapped_pending_count(self):
        for wizard in self:
            wizard.unmapped_pending_count = len(wizard.unmapped_ids.filtered(lambda u: not u.target))

    @api.depends('move_id')
    def _compute_has_existing_lines(self):
        for wizard in self:
            wizard.has_existing_lines = bool(wizard.move_id.invoice_line_ids)

    # -------------------------------------------------------------------------
    # UNMAPPED DATA PLACEMENT
    # -------------------------------------------------------------------------

    @api.onchange('unmapped_ids')
    def _onchange_unmapped_ids(self):
        errors = self._apply_unmapped()
        if errors:
            return {'warning': {'title': self.env._("Some data could not be placed"), 'message': '\n'.join(errors)}}

    def _apply_unmapped(self):
        """Move every unmapped datum whose destination was chosen into that destination.

        Each row is applied once per destination (``applied_target``) so the onchange and the
        confirmation can both call this method safely.
        :returns: list of error messages for rows that could not be applied.
        """
        errors = []
        for row in self.unmapped_ids:
            if not row.target or row.target == row.applied_target:
                continue
            error = row.target != 'discard' and self._apply_unmapped_row(row)
            if error:
                errors.append(error)
                continue
            row.applied_target = row.target
        return errors

    def _apply_unmapped_row(self, row):
        value = (row.value or '').strip()
        target = row.target
        if target in CHAR_TARGETS:
            self[target] = value
        elif target in DATE_TARGETS:
            date = _to_date(value)
            if not date:
                return self.env._("'%(label)s': '%(value)s' is not a valid date.", label=row.label, value=value)
            self[target] = date
        elif target == 'narration':
            text = f"{row.label}: {value}" if row.label else value
            self.narration = f"{self.narration}\n{text}" if self.narration else text
        elif target == 'line':
            try:
                price = _to_float(value)
                name = row.label or value
            except ValueError:
                price = 0.0
                name = f"{row.label}: {value}" if row.label else value
            self.line_ids = [Command.create({
                'sequence': (max(self.line_ids.mapped('sequence')) + 1) if self.line_ids else 10,
                'name': name,
                'quantity': 1.0,
                'price_unit': price,
            })]
        return False

    # -------------------------------------------------------------------------
    # EXTRACTION
    # -------------------------------------------------------------------------

    def _get_claude_settings(self):
        icp = self.env['ir.config_parameter'].sudo()
        return {
            'api_key': icp.get_str('odossey_invoice_claude_ocr.api_key') or os.environ.get('ANTHROPIC_API_KEY'),
            'model': icp.get_str('odossey_invoice_claude_ocr.model') or claude_client.DEFAULT_MODEL,
            'max_tokens': icp.get_int('odossey_invoice_claude_ocr.max_tokens') or claude_client.DEFAULT_MAX_TOKENS,
            'extra_instructions': icp.get_str('odossey_invoice_claude_ocr.instructions') or None,
        }

    def action_read(self):
        """Send the document to Claude and fill the wizard with the result."""
        self.ensure_one()
        if not self.file:
            raise UserError(self.env._("Upload the invoice document (PDF or image) first."))
        if self.mimetype not in claude_client.SUPPORTED_MIMETYPES:
            raise UserError(self.env._(
                "Unsupported file type %(mimetype)s. Use a PDF, JPG, PNG, GIF or WEBP file.",
                mimetype=self.mimetype or '?'))
        settings = self._get_claude_settings()
        raw = self.file.content
        try:
            result = claude_client.extract_invoice(
                settings['api_key'], raw, self.mimetype,
                model=settings['model'], max_tokens=settings['max_tokens'],
                extra_instructions=settings['extra_instructions'],
            )
        except claude_client.ClaudeError as e:
            raise UserError(self.env._("Claude could not digitize the document:\n%s", e)) from e
        self.line_ids.unlink()
        self.unmapped_ids.unlink()
        self.write(self._prepare_values_from_result(result, settings['model']))
        return self._action_open()

    def _prepare_values_from_result(self, result, model_name=None):
        """Convert the Claude JSON result into wizard values."""
        self.ensure_one()
        company = self.company_id
        supplier = result.get('supplier') or {}
        unmapped = [
            {'label': item.get('label') or '', 'value': item.get('value') or ''}
            for item in result.get('unmapped') or []
            if item.get('value')
        ]

        vals = {
            'state': 'review',
            'claude_model': model_name,
            'raw_result': result,
            'supplier_name': supplier.get('name') or False,
            'supplier_vat': supplier.get('vat') or False,
            'supplier_street': supplier.get('street') or False,
            'supplier_city': supplier.get('city') or False,
            'supplier_zip': supplier.get('zip') or False,
            'supplier_email': supplier.get('email') or False,
            'supplier_phone': supplier.get('phone') or False,
            'iban': supplier.get('iban') or False,
            'ref': result.get('invoice_number') or False,
            'payment_reference': result.get('payment_reference') or False,
            'invoice_origin': result.get('purchase_order') or False,
            'amount_untaxed_read': result.get('amount_untaxed') or 0.0,
            'amount_tax_read': result.get('amount_tax') or 0.0,
            'amount_total_read': result.get('amount_total') or 0.0,
        }
        if supplier.get('country_code'):
            country = self.env['res.country'].search([('code', '=ilike', supplier['country_code'])], limit=1)
            vals['supplier_country_id'] = country.id
        if result.get('document_type') == 'credit_note':
            vals['move_type'] = 'in_refund'

        for key in DATE_TARGETS:
            printed = result.get('due_date' if key == 'invoice_date_due' else key)
            date = _to_date(printed)
            vals[key] = date or False
            if printed and not date:
                unmapped.append({'label': dict(TARGET_SELECTION)[key], 'value': printed})

        if code := (result.get('currency') or '').strip():
            currency = self.env['res.currency'].search([('name', '=ilike', code)], limit=1)
            if currency:
                vals['currency_id'] = currency.id
            else:
                unmapped.append({'label': self.env._("Currency (not active)"), 'value': code})

        partner = self._find_partner(supplier)
        vals['partner_id'] = partner.id

        sign = -1 if (result.get('amount_total') or 0.0) < 0 and vals.get('move_type', self.move_type) == 'in_refund' else 1
        if sign < 0:
            for key in ('amount_untaxed_read', 'amount_tax_read', 'amount_total_read'):
                vals[key] = -vals[key]
        vals['line_ids'] = [
            Command.create(self._prepare_line_values(line, sequence, sign))
            for sequence, line in enumerate(result.get('lines') or [], start=1)
        ]
        vals['unmapped_ids'] = [Command.create(item) for item in unmapped]

        low = [
            CONFIDENCE_FIELDS.get(item.get('field'), item.get('field'))
            for item in result.get('confidence') or []
            if item.get('level') == 'low'
        ]
        vals['low_confidence'] = ', '.join(low) or False
        return vals

    def _find_partner(self, supplier):
        company = self.company_id
        partner = self.env['res.partner']
        if supplier.get('vat') or supplier.get('name') or supplier.get('email') or supplier.get('phone'):
            partner = partner._retrieve_partner(
                name=supplier.get('name') or None,
                vat=supplier.get('vat') or None,
                email=supplier.get('email') or None,
                phone=supplier.get('phone') or None,
                company=company,
            )
        if not partner and supplier.get('iban'):
            bank = self.env['res.partner.bank'].search([
                *self.env['res.partner.bank']._check_company_domain(company),
                ('sanitized_account_number', '=', sanitize_account_number(supplier['iban'])),
            ], limit=1)
            partner = bank.partner_id
        # Never propose one of our own companies as vendor.
        if partner and partner.commercial_partner_id in self.env['res.company'].sudo().search([]).partner_id:
            partner = self.env['res.partner']
        return partner.commercial_partner_id if partner else partner

    def _prepare_line_values(self, line, sequence, sign=1):
        product = self.env['product.product']
        if line.get('description') or line.get('product_code'):
            product = product._retrieve_product(
                company=self.company_id,
                name=line.get('description') or None,
                default_code=line.get('product_code') or None,
            )
        rate = line.get('tax_rate_pct')
        taxes = self._find_taxes(rate, product)
        return {
            'sequence': sequence * 10,
            'name': line.get('description') or line.get('product_code') or '/',
            'product_code': line.get('product_code') or False,
            'product_id': product.id,
            'quantity': line.get('quantity') or 1.0,
            'price_unit': sign * (line.get('unit_price') or 0.0),
            'discount': line.get('discount_pct') or 0.0,
            'tax_rate_read': rate if rate is not None else False,
            'tax_ids': [Command.set(taxes.ids)],
        }

    def _find_taxes(self, rate, product=None):
        Tax = self.env['account.tax']
        if rate is None:
            return Tax

        def matches(tax):
            return tax.amount_type == 'percent' and float_compare(tax.amount, rate, precision_digits=2) == 0

        if product:
            taxes = product.supplier_taxes_id.filtered(
                lambda t: matches(t) and (not t.company_id or t.company_id in self.company_id.parent_ids))
            if taxes:
                return taxes[:1]
        taxes = Tax.search(
            Domain(Tax._check_company_domain(self.company_id)) & Domain([
                ('type_tax_use', '=', 'purchase'),
                ('amount_type', '=', 'percent'),
                ('amount', '=', rate),
            ]),
            order='sequence, id',
        )
        # Prefer taxes excluded from the price, as amounts read are usually net prices.
        return taxes.sorted(lambda t: t.price_include)[:1]

    # -------------------------------------------------------------------------
    # CONFIRMATION
    # -------------------------------------------------------------------------

    def action_confirm(self):
        """Write the data reviewed in the wizard into a draft vendor bill."""
        self.ensure_one()
        if self.state != 'review':
            raise UserError(self.env._("Read the document with Claude first."))
        pending = self.unmapped_ids.filtered(lambda u: not u.target)
        if pending:
            raise UserError(self.env._(
                "Choose a destination (or 'Discard') for every datum Claude could not place:\n%s",
                '\n'.join(f"- {u.label}: {u.value}" for u in pending)))
        errors = self._apply_unmapped()
        if errors:
            raise UserError('\n'.join(errors))
        if self.move_id and self.move_id.state != 'draft':
            raise UserError(self.env._("The vendor bill %s is not in draft anymore.", self.move_id.display_name))

        partner = self.partner_id or self._create_partner()
        move = self.move_id or self.env['account.move'].with_company(self.company_id).create({
            'move_type': self.move_type,
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
        })
        if move.move_type != self.move_type:
            move.move_type = self.move_type

        with move._get_edi_creation() as move:
            move.write(self._prepare_move_values(partner))
        if self.invoice_date_due and move.invoice_date_due != self.invoice_date_due:
            # The due date printed on the document wins over the vendor's payment terms.
            move.write({'invoice_payment_term_id': False, 'invoice_date_due': self.invoice_date_due})
        if self.amount_total_read and abs(move.amount_total - self.amount_total_read) <= 0.05:
            move._check_total_amount(self.amount_total_read)

        self._post_document_on_move(move)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    def _create_partner(self):
        if not self.create_partner or not self.supplier_name:
            return self.env['res.partner']
        return self.env['res.partner'].create({
            'name': self.supplier_name,
            'is_company': True,
            'vat': self.supplier_vat,
            'street': self.supplier_street,
            'city': self.supplier_city,
            'zip': self.supplier_zip,
            'country_id': self.supplier_country_id.id,
            'email': self.supplier_email,
            'phone': self.supplier_phone,
            'company_id': False,
        })

    def _prepare_move_values(self, partner):
        vals = {
            'partner_id': partner.id,
            'ref': self.ref,
            'invoice_date': self.invoice_date,
            'currency_id': self.currency_id.id or self.company_id.currency_id.id,
            'invoice_origin': self.invoice_origin,
            'narration': self.narration,
            'invoice_line_ids': [Command.clear()] + [
                Command.create(line._prepare_move_line_values()) for line in self.line_ids
            ],
        }
        if self.payment_reference:
            vals['payment_reference'] = self.payment_reference
        if self.iban and partner:
            vals['partner_bank_id'] = self._get_partner_bank(partner).id
        return vals

    def _get_partner_bank(self, partner):
        try:
            return self.env['res.partner.bank']._find_or_create_bank_account(
                account_number=self.iban, partner=partner, company=self.company_id)
        except UserError as e:
            _logger.info("Bank account %s not set on vendor bill: %s", self.iban, e)
            return self.env['res.partner.bank']

    def _post_document_on_move(self, move):
        body = self.env._("Bill data digitized with Claude (%s) and confirmed by the user.",
                          self.claude_model or claude_client.DEFAULT_MODEL)
        attachment = self.attachment_id
        if not attachment and self.file:
            attachment = self.env['ir.attachment'].create({
                'name': self.file_name or 'invoice',
                'raw': self.file.content,
                'mimetype': self.mimetype,
                'res_model': 'account.move',
                'res_id': move.id,
            })
            move.with_context(disable_attachment_import=True).message_post(body=body, attachment_ids=attachment.ids)
            move._message_set_main_attachment_id(attachment, force=True)
        else:
            move.message_post(body=body)

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------

    def _action_open(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Digitize with Claude"),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {**self.env.context, 'dialog_size': 'extra-large'},
        }


class ClaudeInvoiceWizardLine(models.TransientModel):
    _name = 'claude.invoice.wizard.line'
    _description = "Invoice Digitization with Claude - Line"
    _order = 'sequence, id'

    wizard_id = fields.Many2one('claude.invoice.wizard', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='wizard_id.company_id')
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Description", required=True)
    product_code = fields.Char(string="Code (read)")
    product_id = fields.Many2one(
        'product.product', string="Product",
        domain="[('company_id', 'in', (False, company_id))]",
    )
    quantity = fields.Float(default=1.0, digits='Product Unit')
    price_unit = fields.Float(string="Unit Price", digits='Product Price')
    discount = fields.Float(string="Disc.%", digits='Discount')
    tax_rate_read = fields.Float(string="Tax % (read)")
    tax_ids = fields.Many2many(
        'account.tax', string="Taxes",
        domain="[('type_tax_use', '=', 'purchase'), ('company_id', 'parent_of', company_id)]",
    )
    price_subtotal = fields.Float(string="Subtotal", compute='_compute_price_subtotal', digits='Account')

    @api.depends('quantity', 'price_unit', 'discount')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit * (1 - (line.discount or 0.0) / 100.0)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and not self.tax_ids:
            taxes = self.product_id.supplier_taxes_id.filtered(
                lambda t: not t.company_id or t.company_id in self.company_id.parent_ids)
            if not float_is_zero(self.tax_rate_read, precision_digits=2):
                taxes = taxes.filtered(lambda t: float_compare(t.amount, self.tax_rate_read, precision_digits=2) == 0)
            self.tax_ids = taxes

    def _prepare_move_line_values(self):
        vals = {
            'sequence': self.sequence,
            'name': self.name,
            'quantity': self.quantity,
            'price_unit': self.price_unit,
            'discount': self.discount,
        }
        if self.product_id:
            vals['product_id'] = self.product_id.id
        if self.tax_ids:
            vals['tax_ids'] = [Command.set(self.tax_ids.ids)]
        return vals


class ClaudeInvoiceWizardUnmapped(models.TransientModel):
    _name = 'claude.invoice.wizard.unmapped'
    _description = "Invoice Digitization with Claude - Data to place"
    _order = 'id'

    wizard_id = fields.Many2one('claude.invoice.wizard', required=True, ondelete='cascade')
    label = fields.Char(string="Label (read)")
    value = fields.Char(string="Value (read)")
    target = fields.Selection(TARGET_SELECTION, string="Place in")
    applied_target = fields.Char()
