# -*- coding: utf-8 -*-
# Copyright (C) 2021-Today: Part of Odossey.
# @author:  Part of Odossey.
from odoo import fields, models

from .claude_client import DEFAULT_MAX_TOKENS, DEFAULT_MODEL

CLAUDE_MODELS = [
    ('claude-haiku-5-5', 'Claude Haiku 5.5 (fast, cheapest)'),
    ('claude-sonnet-5-5', 'Claude Sonnet 5.5 (balanced)'),
    ('claude-opus-5-5', 'Claude Opus 5.5 (most accurate)'),
]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    claude_ocr_api_key = fields.Char(
        string="Anthropic API Key",
        config_parameter='odossey_invoice_claude_ocr.api_key',
        help="If empty, the ANTHROPIC_API_KEY environment variable of the server is used.",
    )
    claude_ocr_model = fields.Selection(
        CLAUDE_MODELS,
        string="Claude Model",
        default=DEFAULT_MODEL,
        config_parameter='odossey_invoice_claude_ocr.model',
    )
    claude_ocr_max_tokens = fields.Integer(
        string="Max Output Tokens",
        default=DEFAULT_MAX_TOKENS,
        config_parameter='odossey_invoice_claude_ocr.max_tokens',
    )
    claude_ocr_instructions = fields.Char(
        string="Extra Instructions",
        config_parameter='odossey_invoice_claude_ocr.instructions',
        help="Additional instructions sent to Claude with every document "
             "(e.g. 'Withholding taxes must be reported in unmapped data').",
    )
