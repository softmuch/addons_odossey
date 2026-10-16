# -*- coding: utf-8 -*-
# Copyright (C) 2021-Today: Part of Odossey.
# @author:  Part of Odossey.
from odoo import models
from odoo.exceptions import UserError

from .claude_client import SUPPORTED_MIMETYPES


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_claude_ocr_attachment(self):
        self.ensure_one()
        candidates = self.message_main_attachment_id | self.import_source_attachment_id
        candidates |= self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
        ], order='id desc')
        return candidates.filtered(lambda a: a.mimetype in SUPPORTED_MIMETYPES)[:1]

    def action_claude_digitize(self):
        self.ensure_one()
        if self.state != 'draft' or self.move_type not in ('in_invoice', 'in_refund'):
            raise UserError(self.env._("Only draft vendor bills and credit notes can be digitized with Claude."))
        attachment = self._get_claude_ocr_attachment()
        if not attachment:
            raise UserError(self.env._(
                "Attach the invoice document (PDF or image) to this bill before digitizing it with Claude."))
        wizard = self.env['claude.invoice.wizard'].create({
            'move_id': self.id,
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'move_type': self.move_type,
            'attachment_id': attachment.id,
            'file': attachment.raw,
            'file_name': attachment.name,
        })
        wizard.action_read()
        return wizard._action_open()
