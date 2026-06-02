import logging
import psycopg2

from odoo import models, fields, tools, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrderV2(models.Model):
    _inherit = "pos.order"

    is_split = fields.Boolean("Is Split bill", default=False)
    to_split = fields.Integer("To Split", default=1)
    split_done = fields.Integer("Split Done", default=0)
    n_payments = fields.Integer("Nº Payments", default=1)
    split_invoice_ids = fields.Many2many(
        'account.move',
        'pos_order_split_invoice_rel',
        'order_id',
        'invoice_id',
        string='Split Invoices',
    )

    def action_view_split_invoices(self):
        """Open the list of split invoices for this order."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Split Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.split_invoice_ids.ids)],
            'context': {'default_move_type': 'out_invoice'},
        }

    def _process_saved_order(self, draft):
        """Override for split orders: skip base _generate_pos_order_invoice.

        When all split payments are accumulated the base action_pos_order_paid()
        succeeds, which would trigger _generate_pos_order_invoice() and create
        a full-amount invoice. For split orders we handle invoicing per-round in
        _process_order instead, so we skip that step here.
        """
        if self.is_split and self.to_split > 1:
            if not draft and self.state != 'cancel':
                try:
                    self.action_pos_order_paid()
                except psycopg2.DatabaseError:
                    raise
                except Exception as e:
                    _logger.error(
                        'Could not fully process the POS Order: %s',
                        tools.exception_to_unicode(e),
                    )
            self._create_order_picking()
            self._compute_total_cost_in_real_time()
            # Intentionally skip _generate_pos_order_invoice — split invoices
            # are created per-payment round in _process_order.
            return self.id
        return super()._process_saved_order(draft)

    def bill_made(self, order_id):
        order = self.browse(order_id)
        if order and order.is_split:
            res = order.write({"split_done": order.split_done + 1})
            return res

    def _process_order(self, order, existing_order):
        old_split_done = existing_order.split_done if existing_order else 0
        # Capture payment IDs BEFORE super() so we can identify which payments
        # are NEW in this round (vs accumulated from previous rounds).
        old_payment_ids = set(existing_order.payment_ids.ids) if existing_order else set()
        result_id = super()._process_order(order, existing_order)

        pos_order = self.env['pos.order'].browse(result_id)
        n_payments_this_round = pos_order.split_done - old_split_done

        # Note: state and amount_paid are handled by action_pos_order_paid() inside
        # _process_saved_order, which now succeeds because payments accumulate across
        # split rounds. The forced write is no longer needed.

        # Create an invoice immediately when this sync round carries an invoice
        # request (to_invoice=True) and there are payments for this round.
        # After creating the invoice we reset to_invoice=False so the next
        # person's sync starts fresh without triggering another invoice.
        if (pos_order.is_split
                and pos_order.to_invoice
                and n_payments_this_round > 0):
            if pos_order.payment_ids and pos_order.amount_total and pos_order.to_split:
                # Identify payments added in THIS round by diffing against what
                # existed before super() ran. This is correct even when one person
                # pays for multiple shares (n_payments_this_round > 1 but still
                # only 1 new payment line).
                new_payment_ids = set(pos_order.payment_ids.ids) - old_payment_ids
                if not new_payment_ids:
                    # Fallback: take the last payment line (handles auto-sync edge case)
                    new_payment_ids = {pos_order.payment_ids.sorted('id')[-1].id}
                pos_order._generate_split_invoice_for_payment(
                    n_payments_this_round, new_payment_ids
                )
            # Do NOT reset to_invoice here. Keeping it True means the button
            # stays highlighted for the next person — they can turn it off if
            # they don't want an invoice. This avoids requiring each person to
            # re-press the button. Spurious re-triggering is prevented because
            # the condition requires n_payments_this_round > 0, which only
            # occurs when split_done increments (i.e., on _finalizeValidation syncs).

        return result_id

    def _generate_split_invoice_for_payment(self, n_payments, payment_ids_for_round=None):
        """Create one invoice covering n_payments/to_split of the order.

        Each line uses price_unit * factor and its description gets
        '(div en {to_split})' appended. The payments in payment_ids_for_round
        are reconciled against this invoice.

        NOTE: We intentionally exclude 'pos_order_ids' from move_vals so that
        Odoo's One2many inverse does NOT overwrite pos_order.account_move when
        the invoice is created. Instead we manage split_invoice_ids ourselves
        and only set account_move on the first invoice.
        """
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Please provide a partner for the sale.'))

        # Derive factor from the actual payment amount so the invoice total
        # matches what was paid exactly (avoids "partially paid" from rounding).
        payments = self.env['pos.payment'].browse(list(payment_ids_for_round)) if payment_ids_for_round else None
        if payments and self.amount_total:
            factor = sum(p.amount for p in payments) / self.amount_total
        else:
            factor = n_payments / self.to_split

        move_vals = self._prepare_invoice_vals()

        # Remove pos_order_ids so the ORM does NOT update pos_order.account_move
        # via the One2many inverse when creating the split invoice.
        move_vals.pop('pos_order_ids', None)

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

        # Track this invoice in split_invoice_ids.
        self.write({'split_invoice_ids': [(4, new_move.id)]})

        # Set account_move only if this is the first split invoice; subsequent
        # invoices must not overwrite it so the order remains in "invoiced" state.
        if not self.account_move:
            self.write({'account_move': new_move.id})

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
