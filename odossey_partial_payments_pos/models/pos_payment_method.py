# -*- coding: utf-8 -*-
# Copyright (C) 2026-Today: Part of Odossey.
# @author:  Part of Odossey.

from odoo import fields, models

CREDIT_METHOD_NAME = 'Crédito Cliente'


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    is_credit_transfer = fields.Boolean(
        default=False,
        help='Internal, non-cash tender used only to move already-collected '
        'money between orders (overpayment redistribution) or to apply a '
        "previously banked customer credit -- never represents real cash/"
        'bank movement, so it needs no journal.',
    )

    def _get_or_create_credit_payment_method(self, company):
        """Find-or-create the dedicated internal "Crédito Cliente" tender for
        `company`, and make sure it's usable on every one of that company's
        POS configs (adding a brand new config later still needs this run
        again, or the config's own default payment methods won't include
        it).
        """
        method = self.sudo().search([
            ('company_id', '=', company.id), ('is_credit_transfer', '=', True),
        ], limit=1)
        if not method:
            method = self.sudo().create({
                'name': CREDIT_METHOD_NAME,
                'company_id': company.id,
                'is_credit_transfer': True,
                # No journal_id on purpose: `_compute_type` then resolves
                # `type` to 'pay_later', same as core's own "Customer
                # Account" -- no real cash/bank ledger impact.
            })
        configs = self.env['pos.config'].sudo().search([('company_id', '=', company.id)])
        missing = configs.filtered(lambda c: method not in c.payment_method_ids)
        if missing:
            # Core forbids changing `payment_method_ids` on a config with an
            # open session -- exactly the situation this runs in in
            # practice (a live order just got overpaid, or a cashier is
            # about to apply banked credit). Core provides this precise
            # bypass for that reason.
            missing.with_context(bypass_payment_method_ids_forbidden_change=True).write(
                {'payment_method_ids': [(4, method.id)]}
            )
        return method
