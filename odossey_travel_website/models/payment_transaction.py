import logging

from odoo import models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import str2bool

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _travel_orders(self):
        return self.sale_order_ids.filtered('trip_id')

    def _check_amount_and_confirm_order(self):
        """Trips: confirm the booking without breaking the payment post-processing when the
        trip got full in the meantime (the money is already collected: a refund activity is
        created instead), and invoice the online payments so that they freeze the price."""
        travel_txs = self.filtered(lambda tx: len(tx.sale_order_ids) == 1 and tx._travel_orders())
        confirmed = super(PaymentTransaction, self - travel_txs)._check_amount_and_confirm_order()
        auto_invoice = str2bool(
            self.env['ir.config_parameter'].sudo().get_param('sale.automatic_invoice'))
        for tx in travel_txs:
            order = tx.sale_order_ids
            if order.state in ('draft', 'sent') and order._is_confirmation_amount_reached():
                try:
                    with self.env.cr.savepoint():
                        order.with_context(send_email=True).action_confirm()
                    confirmed |= order
                except (UserError, ValidationError) as error:
                    _logger.warning("Travel: paid online booking %s not confirmed: %s",
                                    order.name, error)
                    order.message_post(body=self.env._(
                        "The online payment was received but the booking could not be "
                        "confirmed: %s", error))
                    order.activity_schedule(
                        'mail.mail_activity_data_todo',
                        summary=self.env._("Online payment received: booking not confirmed"),
                        note=str(error),
                        user_id=(order.trip_id.user_id or order.user_id or self.env.user).id,
                    )
            if tx.state == 'done' and not auto_invoice:
                tx._travel_invoice_orders()
        return confirmed

    def _invoice_sale_orders(self):
        travel_txs = self.filtered(lambda tx: tx._travel_orders())
        travel_txs._travel_invoice_orders()
        return super(PaymentTransaction, self - travel_txs)._invoice_sale_orders()

    def _travel_invoice_orders(self):
        """Invoice each online payment of a booking: a deposit (down payment) invoice for the
        amount of the transaction, or the final invoice when it pays the rest of the booking.
        Invoices are posted here so that a configuration error does not block the payment."""
        for tx in self.filtered(lambda t: t.state == 'done' and not t.invoice_ids):
            tx = tx.with_company(tx.company_id)
            invoices = self.env['account.move']
            for order in tx._travel_orders().filtered(lambda o: o.state == 'sale'):
                amount = tx.currency_id._convert(
                    tx.amount, order.currency_id, order.company_id, tx.create_date.date())
                remaining = order.amount_total - order._travel_invoiced_amount()
                try:
                    with self.env.cr.savepoint():
                        if order.currency_id.compare_amounts(amount, remaining) >= 0:
                            invoice = order.with_context(
                                raise_if_nothing_to_invoice=False)._create_invoices(final=True)
                        else:
                            wizard = self.env['sale.advance.payment.inv'].with_context(
                                active_model='sale.order', active_ids=order.ids,
                            ).create({
                                'sale_order_ids': [Command.set(order.ids)],
                                'advance_payment_method': 'fixed',
                                'fixed_amount': amount,
                            })
                            invoice = wizard._create_invoices(order)
                        invoice.action_post()
                    invoices |= invoice
                except (UserError, ValidationError) as error:
                    _logger.warning("Travel: online payment of %s not invoiced: %s",
                                    order.name, error)
                    order.activity_schedule(
                        'mail.mail_activity_data_todo',
                        summary=self.env._("Invoice the online payment %s", tx.reference),
                        note=str(error),
                        user_id=(order.trip_id.user_id or order.user_id or self.env.user).id,
                    )
            for invoice in invoices:
                invoice._portal_ensure_token()
            if invoices:
                tx.invoice_ids = [Command.set(invoices.ids)]
