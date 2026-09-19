# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import formatLang


class PayFreelyWizard(models.TransientModel):
    _name = 'pay.freely.wizard'
    _description = 'Pagar Libremente - Aplica un importe a las órdenes POS más viejas del cliente'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Cliente',
        required=True,
    )
    # Money tendered through `payment_method_id` -- with `use_customer_credit`
    # on, the customer's banked credit is applied ON TOP of it (as its own
    # separate "Crédito Cliente/Proveedor" payment), so it can be 0 when the
    # credit alone covers everything owed.
    amount = fields.Monetary(
        string='Importe a Pagar',
        required=True,
        currency_field='company_currency_id',
    )
    company_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moneda',
        related='company_id.currency_id',
        readonly=True,
        help='Sólo se tomarán en cuenta las órdenes del cliente expresadas en '
        'la moneda de la empresa.',
    )
    payment_method_id = fields.Many2one(
        comodel_name='pos.payment.method',
        string='Método de Pago',
        domain="[('company_id', '=', company_id), ('is_credit_transfer', '=', False)]",
    )
    use_customer_credit = fields.Boolean(string='Usar crédito a favor del cliente', default=True)
    customer_credit_balance = fields.Monetary(
        string='Crédito a favor del cliente',
        currency_field='company_currency_id',
        compute='_compute_customer_credit_balance',
    )
    # Same reasoning as pos.payment/pos.make.payment's own mirrored field
    # (see l10n_latam_check_ext): a dotted `payment_method_id.payment_method_type`
    # in a view `invisible` expression never evaluates -- the client only
    # fetches `display_name` for a plain many2one.
    payment_method_type = fields.Selection(related='payment_method_id.payment_method_type')
    payment_date = fields.Date(
        string='Fecha de Pago',
        required=True,
        default=fields.Date.context_today,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Empresa',
        default=lambda self: self.env.company,
        readonly=True,
    )

    # ── Check fields ─────────────────────────────────────────────────────────
    # This wizard is defined here, not on a core model -- l10n_latam_check_ext
    # (which this module already depends on) can't `_inherit` it to add these
    # the way it does for pos.payment/pos.make.payment, since that would make
    # l10n_latam_check_ext depend back on odossey_pos_edit_backend (circular).
    # So the check fields/logic live directly in this same module instead, only
    # reusing l10n_latam_check_ext's own helpers (`_l10n_latam_check_require_real_partner`,
    # `res.partner._run_vat_checks`).
    l10n_latam_check_number = fields.Char(string="Número de Cheque")
    l10n_latam_check_bank_id = fields.Many2one("res.bank", string="Banco Emisor")
    l10n_latam_check_issuer_vat = fields.Char(string="CUIT Emisor")
    l10n_latam_check_type = fields.Selection(
        selection=[
            ("common", "Cheque Común"),
            ("deferred", "Cheque de Pago Diferido (CPD)"),
            ("echeq", "ECHEQ o Cheque Electrónico"),
        ],
        string="Tipo de Cheque",
    )
    l10n_latam_check_issue_date = fields.Date(string="Fecha de Emisión")
    l10n_latam_check_payment_date = fields.Date(string="Fecha de Cobro")

    @api.onchange('payment_method_id')
    def _onchange_payment_method_id_l10n_latam_check(self):
        if (
            self.payment_method_id.payment_method_type == 'check'
            and not self.l10n_latam_check_issuer_vat
            and self.partner_id.vat
        ):
            self.l10n_latam_check_issuer_vat = self.partner_id.vat

    @api.depends('partner_id')
    def _compute_customer_credit_balance(self):
        for wizard in self:
            wizard.customer_credit_balance = wizard.partner_id.pos_credit_balance

    def _get_default_amount(self):
        """The customer's outstanding total across their open POS orders,
        net of the banked credit that would be applied to it -- the common
        case is paying it off in full, so this saves re-typing that total."""
        self.ensure_one()
        total = self._get_total_residual()
        if self.use_customer_credit:
            total -= min(max(self.customer_credit_balance, 0.0), total)
        return self.company_currency_id.round(total)

    def _get_credit_to_apply(self):
        """Credit consumed: it covers whatever the typed `amount` leaves
        uncovered (up to the balance), like purchase orders' supplier credit."""
        self.ensure_one()
        if not self.use_customer_credit:
            return 0.0
        gap = self._get_total_residual() - self.amount
        return self.company_currency_id.round(
            min(max(self.customer_credit_balance, 0.0), max(gap, 0.0))
        )

    @api.onchange('partner_id', 'use_customer_credit')
    def _onchange_partner_id_amount(self):
        if self.partner_id:
            self.amount = self._get_default_amount()

    @api.constrains('amount')
    def _check_amount(self):
        for wizard in self:
            if wizard.amount < 0:
                raise ValidationError(_('El importe a pagar no puede ser negativo.'))

    def _get_open_orders(self):
        self.ensure_one()
        orders = self.env['pos.order'].search([
            ('partner_id', '=', self.partner_id.id),
            ('state', 'in', ('draft', 'partially_paid')),
            ('currency_id', '=', self.company_currency_id.id),
            ('company_id', '=', self.company_id.id),
        ], order='date_order asc, id asc')
        # An order that's already fully paid or overpaid (e.g. `partially_paid`
        # only because of a since-corrected overpayment) has a zero/negative
        # residual -- including it here would drag the customer's total
        # residual negative, defaulting `amount` to a negative value that
        # then can never be raised back up (see `_onchange_amount_cap`: any
        # positive amount "exceeds" a negative total_residual and gets
        # snapped back down). Same filter the purchase-side sibling already
        # applies (`purchase.order.pay.freely._get_open_orders`).
        return orders.filtered(lambda o: o.amount_total - o.amount_paid > 0)

    def _get_total_residual(self):
        self.ensure_one()
        return sum(order.amount_total - order.amount_paid for order in self._get_open_orders())

    def _l10n_latam_check_create(self):
        """Validate the check fields and create ONE `l10n_latam.check` for
        the wizard's full amount -- the same physical check may end up
        settling several orders (see `action_pay`), so it can't be created
        per-payment the way `pos_payment.py`'s instant creation does.
        """
        self.ensure_one()
        self.env['pos.payment']._l10n_latam_check_require_real_partner(self.partner_id)
        if not self.l10n_latam_check_number:
            raise UserError(_("Completá el número de cheque antes de continuar."))
        if self.l10n_latam_check_issuer_vat:
            self.env['res.partner']._run_vat_checks(
                self.company_id.country_id, self.l10n_latam_check_issuer_vat,
                partner_name=_("CUIT Emisor"),
            )
        return self.env['l10n_latam.check'].sudo().create({
            'name': self.l10n_latam_check_number,
            'bank_id': self.l10n_latam_check_bank_id.id,
            'issuer_vat': self.l10n_latam_check_issuer_vat,
            'check_type': self.l10n_latam_check_type,
            'issue_date': self.l10n_latam_check_issue_date,
            'payment_date': (
                self.l10n_latam_check_payment_date
                if self.l10n_latam_check_payment_date else self.payment_date
            ),
            'amount': self.amount,
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
        })

    def _l10n_latam_check_payment_vals(self, check):
        return {
            'l10n_latam_check_number': self.l10n_latam_check_number,
            'l10n_latam_check_bank_id': self.l10n_latam_check_bank_id.id,
            'l10n_latam_check_issuer_vat': self.l10n_latam_check_issuer_vat,
            'l10n_latam_check_type': self.l10n_latam_check_type,
            'l10n_latam_check_issue_date': self.l10n_latam_check_issue_date,
            'l10n_latam_check_payment_date': self.l10n_latam_check_payment_date,
            'l10n_latam_check_id': check.id,
        }

    def _apply_payment(self):
        """Pay the customer's oldest open POS orders first with the given
        amount, creating one `pos.payment` per order reached (instead of an
        `account.payment` against invoices, as this wizard used to do).

        The last order reached may end up partially paid. Unlike the old
        invoice-based version, there's no "free"/advance payment fallback
        for a leftover amount here -- pos.order has no such concept, so an
        amount exceeding the total outstanding is rejected upfront instead.

        If paying by check, ONE `l10n_latam.check` is created for the whole
        amount and linked to every `pos.payment` this creates -- one check
        can now settle several orders at once.

        Shared by `action_pay` (backend) and `pay_from_pos` (POS frontend,
        via the "Pagar Libremente" button in the Actions popup) so both
        entry points run the exact same logic.
        """
        self.ensure_one()
        currency = self.company_currency_id
        orders = self._get_open_orders()
        total_residual = self._get_total_residual()
        # An `amount` above what's owed is allowed (any payment method): the
        # excess goes to the last order reached, which ends up overpaid, and
        # `_process_saved_order` -> `_redistribute_overpayment` (see
        # odossey_partial_payments_pos) banks it as customer credit.

        credit_to_apply = self._get_credit_to_apply()
        # A 0 `amount` is only valid when the credit is about to cover it
        # all -- otherwise it's a no-op the user almost surely didn't intend.
        if self.amount <= 0 and credit_to_apply <= 0:
            raise UserError(_('El importe a pagar debe ser mayor a cero.'))
        if self.amount > 0 and not self.payment_method_id:
            raise UserError(_('Elegí un método de pago.'))

        # Everything below runs `_process_saved_order` itself, once per
        # order: don't let it ALSO auto-consume credit (see
        # `skip_auto_customer_credit` in odossey_partial_payments_pos).
        orders = orders.with_context(skip_auto_customer_credit=True)
        touched = self.env['pos.order']
        credit_applied = 0.0
        credit_left = credit_to_apply
        for order in orders:
            if currency.is_zero(credit_left):
                break
            applied = order.apply_customer_credit(max_amount=credit_left)
            if applied:
                credit_left = currency.round(credit_left - applied)
                credit_applied += applied
                touched |= order

        check = False
        if self.amount > 0 and self.payment_method_id.payment_method_type == 'check':
            check = self._l10n_latam_check_create()

        available = self.amount
        payments = self.env['pos.payment']
        owing = orders.filtered(
            lambda o: o.currency_id.round(o.amount_total - o._compute_amount_paid()) > 0
        )
        # Any excess over what's owed lands on the last order reached.
        last_order = (owing or orders)[-1:]
        for order in orders:
            if currency.is_zero(available):
                break
            residual = order.currency_id.round(order.amount_total - order._compute_amount_paid())
            if (currency.is_zero(residual) or residual < 0) and order != last_order:
                continue
            pay_amount = available if order == last_order else min(available, residual)

            payment_vals = {
                'pos_order_id': order.id,
                'amount': pay_amount,
                'name': self.payment_method_id.name,
                'payment_method_id': self.payment_method_id.id,
                'payment_date': self.payment_date,
            }
            if check:
                payment_vals.update(self._l10n_latam_check_payment_vals(check))
            payments |= self.env['pos.payment'].create(payment_vals)
            touched |= order
            available -= pay_amount

        for order in touched:
            order.amount_paid = order._compute_amount_paid()
            order._process_saved_order(False)
        # Money collected after the session closed has no closing entry to
        # land in: book it as a real account.payment (see
        # `pos.payment._create_late_account_payments`).
        payments._create_late_account_payments()
        paid_orders = touched

        return {
            'payments': payments,
            'orders': paid_orders,
            'applied': self.amount - available + credit_applied,
            'credit_applied': credit_applied,
        }

    def action_pay(self):
        self._apply_payment()
        return True

    @api.model
    def get_partner_debt_info(self, partner_id):
        """RPC entry point for the POS frontend's "Pagar Libremente" button
        (see control_buttons_patch.js): how much this partner currently owes
        across their open POS orders, before the cashier opens the payment
        popup. Uses a non-persisted `new()` record -- no need to actually
        create a wizard just to read this.
        """
        wizard = self.new({'partner_id': partner_id})
        total = wizard._get_total_residual()
        return {
            'total_residual': total,
            'credit_balance': min(max(wizard.customer_credit_balance, 0.0), total),
            'currency_id': wizard.company_currency_id.id,
        }

    @api.model
    def pay_from_pos(self, vals):
        """RPC entry point for the POS frontend's "Pagar Libremente" button:
        creates the wizard record with the vals collected in the popup and
        applies the payment immediately, returning a small JSON-friendly
        summary instead of the backend's `ir.actions.act_window` (meaningless
        to the POS frontend, which just needs to know how it went)."""
        wizard = self.create(vals)
        result = wizard._apply_payment()
        return {
            'orders_count': len(result['orders']),
            'applied': result['applied'],
            'remaining': wizard._get_total_residual(),
        }
