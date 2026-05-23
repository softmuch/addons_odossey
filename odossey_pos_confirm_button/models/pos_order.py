from odoo import api, models, _
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def force_confirm_order(self, order_uuid, payments):
        """
        Force-confirm a POS order stuck in 'draft' after a fiscal printer error.

        Payment strategy:
        - If JS sent payment lines, create any missing ones (checked by UUID).
        - If JS sent no payment lines AND the order has no payment records in DB,
          create ONE forced payment for the full order total using the first
          payment method available in the session.
        - If the order already has payment records, leave them untouched.

        :param order_uuid: str — the order's UUID from the JS model.
        :param payments: list of dicts — [{payment_method_id, amount, uuid}, ...]
                         May be empty if the printer failed before any payment was recorded.
        :return: dict — {'success': True} or {'success': False, 'error': '...'}
        """
        order = self.search([('uuid', '=', order_uuid)], limit=1)
        if not order:
            return {'success': False, 'error': _('Ordine non trovato: %s') % order_uuid}

        # Already finalized — nothing to do
        if order.state in ('invoiced', 'done', 'paid'):
            return {'success': True}

        if order.state != 'draft':
            return {
                'success': False,
                'error': _('Ordine in stato inatteso: %s') % order.state,
            }

        if not order.lines:
            return {'success': False, 'error': _('L\'ordine non ha righe prodotto.')}

        if payments:
            # JS sent payment lines — create any that don't exist yet (by UUID)
            for p in payments:
                payment_uuid = p.get('uuid') or ''
                existing = (
                    self.env['pos.payment'].search(
                        [('uuid', '=', payment_uuid), ('pos_order_id', '=', order.id)],
                        limit=1,
                    )
                    if payment_uuid
                    else self.env['pos.payment']
                )
                if not existing:
                    self.env['pos.payment'].create({
                        'pos_order_id': order.id,
                        'payment_method_id': int(p['payment_method_id']),
                        'amount': float(p['amount']),
                        'uuid': payment_uuid,
                    })

            # Create change line if customer tendered more than the total
            total_tendered = sum(float(p['amount']) for p in payments)
            amount_return = order.currency_id.round(total_tendered - order.amount_total)
            if amount_return > 0:
                cash_method = order.session_id.payment_method_ids.filtered('is_cash_count')[:1]
                if cash_method:
                    self.env['pos.payment'].create({
                        'pos_order_id': order.id,
                        'payment_method_id': cash_method.id,
                        'amount': -amount_return,
                        'is_change': True,
                    })

        elif not order.payment_ids:
            # No JS payments AND no existing DB records → create one forced payment
            payment_method = order.session_id.payment_method_ids[:1]
            if not payment_method:
                return {'success': False, 'error': _('Nessun metodo di pagamento configurato per questa sessione.')}

            self.env['pos.payment'].create({
                'pos_order_id': order.id,
                'payment_method_id': payment_method.id,
                'amount': order.amount_total,
            })
        # else: order already has payment records in DB → leave them untouched

        # Recompute amount_paid from actual payment records
        order.write({
            'amount_paid': sum(order.payment_ids.mapped('amount'))
        })

        # --- Finalize ---
        try:
            order.action_pos_order_paid()
        except UserError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': _('Errore imprevisto: %s') % str(e)}

        return {'success': True}