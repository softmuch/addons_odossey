from odoo import models, fields, _
from odoo.exceptions import UserError

class PosOrderV2(models.Model):
    _inherit = "pos.order"

    is_split = fields.Boolean("Is Split bill", default=False)
    to_split = fields.Integer("To Split", default=1)
    split_done = fields.Integer("Split Done", default=0)
    n_payments = fields.Integer("Nº Payments", default=1)

    def bill_made(self, order_id):
        order = self.browse(order_id)
        if order and order.is_split:
            res = order.write({"split_done": order.split_done + 1})
            return res

    def _process_order(self, order, existing_order):
        old_split_done = existing_order.split_done if existing_order else 0
        result_id = super()._process_order(order, existing_order)

        pos_order = self.env['pos.order'].browse(result_id)
        n_payments_this_round = pos_order.split_done - old_split_done

        # On final split, force state='paid' — action_pos_order_paid() fails because
        # amount_paid only reflects the last person's payment amount.
        if (pos_order.is_split
                and pos_order.split_done == pos_order.to_split
                and pos_order.state == 'draft'):
            pos_order.write({'amount_paid': pos_order.amount_total, 'state': 'paid'})

        # Create invoices on the final sync only, one per payment that requested it.
        # Each payment line carries its own to_invoice flag (set by the JS before
        # splitDone() runs), so each person independently controls whether they
        # want an invoice.
        if (pos_order.is_split
                and pos_order.split_done == pos_order.to_split
                and pos_order.payment_ids):
            for payment in pos_order.payment_ids:
                if payment.to_invoice:
                    pos_order._generate_split_invoice_for_payment(1, {payment.id})

        return result_id

    def _generate_split_invoice_for_payment(self, n_payments, payment_ids_for_round=None):
        """Create one invoice covering n_payments/to_split of the order.

        Each line uses price_unit * (n_payments / to_split) and its description
        gets '(div en {to_split})' appended. The payments in payment_ids_for_round
        are reconciled against this invoice.
        """
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Please provide a partner for the sale.'))

        factor = n_payments / self.to_split
        move_vals = self._prepare_invoice_vals()

        adjusted_lines = []
        for cmd in move_vals.get('invoice_line_ids', []):
            if cmd[0] == 0:  # Command.create
                line_vals = dict(cmd[2])
                line_vals['price_unit'] = line_vals.get('price_unit', 0.0) * factor
                original_name = line_vals.get('name') or ''
                line_vals['name'] = f'{original_name} (div en {self.to_split})'.strip()
                adjusted_lines.append((0, 0, line_vals))
            else:
                adjusted_lines.append(cmd)
        move_vals['invoice_line_ids'] = adjusted_lines

        new_move = self._create_invoice(move_vals)
        new_move.sudo().with_company(self.company_id).with_context(
            **self._get_invoice_post_context()
        )._post()

        if payment_ids_for_round:
            self._apply_split_payment_to_invoice(new_move, payment_ids_for_round)

        if self.env.context.get('generate_pdf', True):
            new_move.with_context(skip_invoice_sync=True)._generate_and_send()

    def _apply_split_payment_to_invoice(self, invoice_move, payment_ids_set):
        """Reconcile a specific set of pos.payment records with invoice_move.

        Handles the case where Odoo's auto-reconciliation linked the payment's
        credit line to the WRONG invoice (a previously open receivable).
        We detect this and fix it before reconciling with the correct invoice.
        """
        payments = self.env['pos.payment'].browse(list(payment_ids_set))
        if not payments:
            return

        receivable_account = (
            self.env['res.partner']
            ._find_accounting_partner(self.partner_id)
            .with_company(self.company_id)
            .property_account_receivable_id
        )

        payment_moves = payments.sudo().with_company(self.company_id)._create_payment_moves(
            self.session_id.state == 'closed'
        )

        if not receivable_account.reconcile:
            return

        # Flush pending writes and clear ORM cache so we read fresh DB state.
        self.env.flush_all()
        self.env.invalidate_all()

        credit_line_ids = payment_moves._context.get('credit_line_ids', None)
        payment_credit_lines = payment_moves.mapped('line_ids').filtered(
            lambda l: (
                (credit_line_ids and l.id in credit_line_ids) or
                (not credit_line_ids and l.account_id == receivable_account and l.partner_id)
            )
        )

        # Read invoice receivable lines directly from DB (bypass ORM cache).
        invoice_recv_lines = self.env['account.move.line'].search([
            ('move_id', '=', invoice_move.id),
            ('account_id', '=', receivable_account.id),
        ])

        for pay_line in payment_credit_lines:
            if pay_line.reconciled:
                # Check if it's already correctly reconciled with our invoice.
                correct = any(
                    r.debit_move_id.id in invoice_recv_lines.ids
                    for r in pay_line.matched_debit_ids
                )
                if correct:
                    continue  # already done ✓
                # Wrong reconciliation (auto-reconcile linked to another invoice).
                # Remove it so we can reconcile with the correct invoice.
                pay_line.remove_move_reconcile()

        # Now reconcile payment credit with this invoice's open receivable.
        open_invoice_lines = invoice_recv_lines.filtered(lambda l: not l.reconciled)
        unreconciled_pay = payment_credit_lines.filtered(lambda l: not l.reconciled)
        if open_invoice_lines and unreconciled_pay:
            (open_invoice_lines | unreconciled_pay).sudo().with_company(
                self.company_id
            ).reconcile()
