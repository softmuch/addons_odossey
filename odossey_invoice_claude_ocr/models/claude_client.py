# -*- coding: utf-8 -*-
# Copyright (C) 2021-Today: Part of Odossey.
# @author:  Part of Odossey.
"""Thin HTTP client for the Claude Messages API used to digitize invoices.

Plain ``requests`` is used on purpose so the module has no extra Python
dependency.  Structured outputs (``output_config.format``) guarantee that the
answer is valid JSON matching ``INVOICE_SCHEMA``.
"""
import base64
import json
import logging
import time

import requests

_logger = logging.getLogger(__name__)

API_URL = 'https://api.anthropic.com/v1/messages'
API_VERSION = '2023-06-01'
DEFAULT_MODEL = 'claude-haiku-5-5'
DEFAULT_MAX_TOKENS = 8192
TIMEOUT = (10, 180)
RETRY_STATUSES = {429, 500, 504, 529}
MAX_RETRIES = 2

SUPPORTED_MIMETYPES = {
    'application/pdf': 'document',
    'image/jpeg': 'image',
    'image/png': 'image',
    'image/gif': 'image',
    'image/webp': 'image',
}

_PARTY = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['name', 'vat', 'street', 'city', 'zip', 'country_code', 'email', 'phone', 'iban'],
    'properties': {
        'name': {'type': 'string'},
        'vat': {'type': 'string', 'description': 'Tax id exactly as printed, empty if absent.'},
        'street': {'type': 'string'},
        'city': {'type': 'string'},
        'zip': {'type': 'string'},
        'country_code': {'type': 'string', 'description': 'ISO 3166-1 alpha-2, empty if unknown.'},
        'email': {'type': 'string'},
        'phone': {'type': 'string'},
        'iban': {'type': 'string'},
    },
}

INVOICE_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': [
        'document_type', 'supplier', 'customer', 'invoice_number', 'invoice_date', 'due_date',
        'currency', 'payment_reference', 'purchase_order', 'amount_untaxed', 'amount_tax',
        'amount_total', 'lines', 'unmapped', 'confidence',
    ],
    'properties': {
        'document_type': {'type': 'string', 'enum': ['invoice', 'credit_note', 'other']},
        'supplier': _PARTY,
        'customer': _PARTY,
        'invoice_number': {'type': 'string'},
        'invoice_date': {'type': 'string', 'description': 'YYYY-MM-DD or empty.'},
        'due_date': {'type': 'string', 'description': 'YYYY-MM-DD or empty.'},
        'currency': {'type': 'string', 'description': 'ISO 4217 code, empty if unknown.'},
        'payment_reference': {'type': 'string'},
        'purchase_order': {'type': 'string'},
        'amount_untaxed': {'type': ['number', 'null']},
        'amount_tax': {'type': ['number', 'null']},
        'amount_total': {'type': ['number', 'null']},
        'lines': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['description', 'product_code', 'quantity', 'unit_price',
                             'discount_pct', 'tax_rate_pct', 'subtotal'],
                'properties': {
                    'description': {'type': 'string'},
                    'product_code': {'type': 'string'},
                    'quantity': {'type': 'number'},
                    'unit_price': {'type': 'number'},
                    'discount_pct': {'type': 'number'},
                    'tax_rate_pct': {'type': ['number', 'null']},
                    'subtotal': {'type': ['number', 'null']},
                },
            },
        },
        'unmapped': {
            'type': 'array',
            'description': 'Every other datum printed on the document that does not fit a known field.',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['label', 'value'],
                'properties': {
                    'label': {'type': 'string'},
                    'value': {'type': 'string'},
                },
            },
        },
        'confidence': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['field', 'level'],
                'properties': {
                    'field': {'type': 'string'},
                    'level': {'type': 'string', 'enum': ['high', 'medium', 'low']},
                },
            },
        },
    },
}

SYSTEM_PROMPT = """You are an accounting data-entry assistant that digitizes vendor invoices.
Rules:
- Read every page. Return only data that is printed on the document; never invent or infer tax ids, IBANs or amounts.
- Use an empty string for text fields that are not present and null for unknown totals.
- Numbers use a dot as decimal separator and no thousands separator (e.g. "1.234,56" -> 1234.56).
- Dates must be ISO formatted YYYY-MM-DD. For ambiguous day/month order use the supplier's country convention.
- "supplier" is the party issuing the invoice, "customer" the party being billed.
- One entry in "lines" per invoice line. quantity defaults to 1 when not printed. discount_pct is 0 when absent.
  tax_rate_pct is the VAT/tax percentage applied to the line (null if not identifiable).
- Put in "unmapped" EVERY other piece of information printed on the document that does not fit one of the
  known fields (e.g. delivery note number, contract number, bank name, BIC/SWIFT, payment terms text, notes,
  shipping address, withholding taxes, stamp duty, customer code). Use the label as printed and the raw value.
  Also report there any inconsistency you notice between the lines and the totals.
- In "confidence" add one entry for supplier.vat, invoice_number, invoice_date, currency and amount_total.
"""


class ClaudeError(Exception):
    """Error raised when the Claude API cannot digitize a document."""


def build_payload(data, mimetype, model=DEFAULT_MODEL, max_tokens=DEFAULT_MAX_TOKENS, extra_instructions=None):
    """Build the Messages API request body for ``data`` (raw bytes)."""
    block_type = SUPPORTED_MIMETYPES.get(mimetype)
    if not block_type:
        raise ClaudeError(f"Unsupported file type: {mimetype}")
    file_block = {
        'type': block_type,
        'source': {
            'type': 'base64',
            'media_type': mimetype,
            'data': base64.b64encode(data).decode(),
        },
    }
    text = "Extract the data of this vendor invoice."
    if extra_instructions:
        text += "\nAdditional instructions:\n" + extra_instructions
    return {
        'model': model,
        'max_tokens': max_tokens,
        'system': [{'type': 'text', 'text': SYSTEM_PROMPT, 'cache_control': {'type': 'ephemeral'}}],
        'output_config': {'format': {'type': 'json_schema', 'schema': INVOICE_SCHEMA}},
        'messages': [{'role': 'user', 'content': [file_block, {'type': 'text', 'text': text}]}],
    }


def parse_response(body):
    """Return the extracted invoice dict from a Messages API response body."""
    stop_reason = body.get('stop_reason')
    if stop_reason == 'max_tokens':
        raise ClaudeError("The answer was truncated (max_tokens reached). Increase the max tokens setting.")
    if stop_reason == 'refusal':
        raise ClaudeError("Claude refused to process this document.")
    text = ''.join(b.get('text', '') for b in body.get('content', []) if b.get('type') == 'text')
    try:
        return json.loads(text)
    except ValueError as e:
        raise ClaudeError(f"Invalid JSON returned by Claude: {e}") from e


def extract_invoice(api_key, data, mimetype, model=DEFAULT_MODEL, max_tokens=DEFAULT_MAX_TOKENS,
                    extra_instructions=None, session=None):
    """Send the document to Claude and return the structured result as a dict."""
    if not api_key:
        raise ClaudeError("The Anthropic API key is not configured.")
    payload = build_payload(data, mimetype, model, max_tokens, extra_instructions)
    headers = {
        'x-api-key': api_key,
        'anthropic-version': API_VERSION,
        'content-type': 'application/json',
    }
    http = session or requests
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = http.post(API_URL, json=payload, headers=headers, timeout=TIMEOUT)
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
                continue
            raise ClaudeError(f"Could not reach the Claude API: {e}") from e
        request_id = response.headers.get('request-id')
        if response.status_code == 200:
            _logger.info("Claude invoice extraction done (request-id %s)", request_id)
            return parse_response(response.json())
        if response.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
            retry_after = response.headers.get('retry-after')
            delay = float(retry_after) if retry_after and retry_after.replace('.', '', 1).isdigit() else 2 ** (attempt + 1)
            _logger.warning("Claude API returned %s (request-id %s), retrying in %ss",
                            response.status_code, request_id, delay)
            time.sleep(min(delay, 30))
            continue
        try:
            message = response.json().get('error', {}).get('message') or response.text
        except ValueError:
            message = response.text
        _logger.warning("Claude API error %s (request-id %s): %s", response.status_code, request_id, message)
        raise ClaudeError(f"Claude API error {response.status_code}: {message}")
    raise ClaudeError("Claude API unavailable, please retry later.")
