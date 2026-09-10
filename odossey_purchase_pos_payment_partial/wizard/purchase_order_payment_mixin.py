# License OPL-1
from odoo import fields, models


class PurchaseOrderPaymentMixin(models.AbstractModel):
    _inherit = 'purchase.order.payment.mixin'

    use_supplier_credit = fields.Boolean(
        default=True, string='Use Supplier Credit'
    )

    def _credit_discounted_amount(self, currency, base_amount, partner):
        """``base_amount`` minus whatever of ``partner``'s banked supplier
        credit would actually apply, capped at the available balance --
        shared by both wizards' ``default_get``/onchange so the displayed
        ``amount`` always matches the ``use_supplier_credit`` checkbox's
        current state. Never caps at a per-order residual here (unlike the
        POS-side equivalent): a leftover beyond what's owed gets
        redistributed/banked instead of rejected, so there's no "residual"
        ceiling to apply credit against upfront.
        """
        if not self.use_supplier_credit or not partner:
            return base_amount
        balance = partner.pos_supplier_credit_balance
        if balance <= 0:
            return base_amount
        applied = min(balance, base_amount)
        return max(currency.round(base_amount - applied), 0.0)

    def _is_free_amount_entry(self):
        # Once this module is installed, an amount exceeding what's owed is
        # never a mistake to reject: it gets redistributed to the
        # supplier's other partially-paid orders and, failing that, banked
        # as reusable credit (see `_redistribute_purchase_overpayment`
        # below) -- the base module's overflow-rejection
        # (`purchase.order.pay.freely.action_pay`) no longer applies.
        return False

    def _get_redistribution_targets(self, partner, company, exclude):
        """This partner's other orders still owing money, oldest first --
        same shape of search as `purchase.order.pay.freely._get_open_orders`,
        but scoped to `payment_status == 'partially_paid'` specifically
        (per the feature's own wording: redirect the excess to already
        partially-paid orders, not to untouched ones)."""
        orders = self.env['purchase.order'].sudo().search([
            ('partner_id', '=', partner.id),
            ('company_id', '=', company.id),
            ('payment_status', '=', 'partially_paid'),
        ], order='date_order asc, id asc')
        return orders - exclude

    def _redistribute_purchase_overpayment(self, primary_order, payment_method, payment_date, remaining):
        """`remaining` is money beyond what `primary_order` itself owes.
        Shift it to the same supplier's other partially-paid orders (oldest
        first), then bank whatever's left as `pos.supplier.credit`. Returns
        the (possibly extended) list of (order, amount) pairs actually
        applied via a real payment, and any amount that ended up banked
        instead of applied to an order.
        """
        self.ensure_one()
        partner = primary_order.partner_id
        company = primary_order.company_id
        order_amounts = []
        for target in self._get_redistribution_targets(partner, company, exclude=primary_order):
            if remaining <= 0:
                break
            residual = target.currency_id.round(target.amount_total - target.amount_paid)
            if residual <= 0:
                continue
            applied = min(remaining, residual)
            order_amounts.append((target, applied))
            remaining = target.currency_id.round(remaining - applied)

        if remaining > 0:
            self._bank_supplier_credit(company, partner, payment_method, payment_date, remaining, primary_order)
            remaining = 0.0

        return order_amounts

    def _bank_supplier_credit(self, company, partner, payment_method, payment_date, amount, origin_order):
        """A real, posted, outbound `account.payment` for `amount`, with
        nothing to reconcile against yet (no bill needs it) -- core's own
        "advance payment" shape (same `write_off_line_vals: []` fix as
        `odossey_purchase_pos_payment`'s own no-open-bill fallback, needed
        for the same reason on a check-coded journal). Consuming this
        credit later (`_consume_supplier_credit_for_order` below)
        reconciles against THIS SAME payment -- no new money ever moves
        twice for the same credit.
        """
        account_payment = self.env['account.payment'].sudo().create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': partner.id,
            'amount': amount,
            'journal_id': payment_method.journal_id.id,
            'date': payment_date,
            'memo': origin_order.name,
            'write_off_line_vals': [],
        })
        account_payment.action_post()
        self.env['pos.supplier.credit'].sudo().create({
            'partner_id': partner.id,
            'company_id': company.id,
            'amount': amount,
            'origin_order_id': origin_order.id,
            'account_payment_id': account_payment.id,
        })

    def _consume_supplier_credit_for_order(self, order, max_amount, payment_method):
        """Consumes up to `max_amount` (and never more than the order's own
        residual) of the supplier's banked credit, oldest banked row first.
        Returns the amount actually consumed, so the caller knows how much
        of what it asked for actually landed.

        Reconciles against a real, already-posted advance payment IF there's
        an open bill to reconcile it against right now. If there isn't (a
        very normal case here: paying a PO before its vendor bill lands),
        the banked advance payment simply stays unreconciled for now -- same
        as a bill-less cash advance (see `pos_payment.py`'s own no-open-bill
        fallback) -- and nets against a future bill later. Either way the
        credit is consumed for THIS order's own bookkeeping below, so
        `amount_paid`/`payment_status` and the credit balance both stay
        truthful regardless of whether a bill exists yet. Never creates a
        new `account.payment` -- the money was already sent to the supplier
        when the credit was banked.

        Also books a purely internal, non-reconciling `pos.payment` for the
        consumed amount (`skip_purchase_order_account_payment` -- the same
        context flag `odossey_purchase_pos_payment_check` already uses to
        avoid a second, redundant `account.payment`), purely so this
        order's own `amount_paid`/`payment_status` stay truthful: without
        this, the order would still look under-paid by exactly the consumed
        amount, contradicting the credit that was just applied to it.
        """
        self.ensure_one()
        partner = order.partner_id
        company = order.company_id
        residual = order.currency_id.round(order.amount_total - order.amount_paid)
        to_consume = min(max_amount, residual)
        if to_consume <= 0:
            return 0.0

        credit_rows = self.env['pos.supplier.credit'].sudo().search([
            ('partner_id', '=', partner.id), ('company_id', '=', company.id), ('amount', '>', 0),
        ], order='date asc, id asc')
        consumed_total = 0.0
        for row in credit_rows:
            if to_consume <= 0:
                break
            used_elsewhere = sum(self.env['pos.supplier.credit'].sudo().search([
                ('account_payment_id', '=', row.account_payment_id.id), ('amount', '<', 0),
            ]).mapped('amount'))
            available = order.currency_id.round(row.amount + used_elsewhere)
            if available <= 0:
                continue
            applied = min(available, to_consume)

            payable_line = row.account_payment_id.move_id.line_ids.filtered(
                lambda line: line.account_id.account_type == 'liability_payable' and not line.reconciled
            )
            bill_lines = order._get_open_bills().line_ids.filtered(
                lambda line: line.account_id.account_type == 'liability_payable' and not line.reconciled
            )
            if payable_line and bill_lines:
                (payable_line | bill_lines).reconcile()

            self.env['pos.supplier.credit'].sudo().create({
                'partner_id': partner.id,
                'company_id': company.id,
                'amount': -applied,
                'used_order_id': order.id,
                'account_payment_id': row.account_payment_id.id,
            })
            to_consume -= applied
            consumed_total += applied

        if consumed_total > 0:
            self.env['pos.payment'].with_context(skip_purchase_order_account_payment=True).create({
                'company_id': order.company_id.id,
                'partner_id': order.partner_id.id,
                'currency_id': order.currency_id.id,
                'amount': -consumed_total,
                'payment_method_id': payment_method.id,
                'purchase_order_id': order.id,
            })
        return consumed_total
