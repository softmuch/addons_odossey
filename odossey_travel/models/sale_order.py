from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import float_compare, float_is_zero, format_date

from .travel_passenger import BOOKING_STATES


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    trip_id = fields.Many2one(
        'travel.trip', string="Trip", index=True, tracking=True, check_company=True,
        domain="[('state', 'in', ('draft', 'open', 'confirmed'))]")
    travel_group_id = fields.Many2one(
        'travel.group', string="Travel Group", index=True, tracking=True, check_company=True,
        domain="[('trip_id', '=', trip_id)]")
    travel_group_type = fields.Selection(related='travel_group_id.group_type')
    travel_passenger_ids = fields.One2many('travel.passenger', 'sale_order_id',
                                           string="Passengers", copy=True)
    travel_pax_count = fields.Integer(string="Passengers Count", compute='_compute_travel_pax',
                                      store=True)
    travel_date_start = fields.Date(related='trip_id.date_start', string="Departure", store=True)
    travel_date_end = fields.Date(related='trip_id.date_end', string="Return")
    travel_balance_due_date = fields.Date(related='trip_id.balance_due_date',
                                          string="Balance Due Date")
    travel_deposit_required = fields.Monetary(
        string="Deposit Required", compute='_compute_travel_deposit_required', store=True,
        help="Deposit the customer must pay to freeze the price of the trip.")
    travel_amount_paid = fields.Monetary(
        string="Paid", compute='_compute_travel_payment', store=True,
        help="Amount paid on the posted customer invoices (deposits included) of the booking, "
             "plus the online payments not reconciled yet.")
    travel_amount_due = fields.Monetary(string="Balance", compute='_compute_travel_payment',
                                        store=True)
    travel_price_frozen = fields.Boolean(
        string="Price Frozen", compute='_compute_travel_payment', store=True,
        help="The deposit has been paid: the price of the booking is frozen.")
    travel_frozen_date = fields.Date(string="Frozen On", compute='_compute_travel_payment',
                                     store=True)
    travel_booking_state = fields.Selection(
        selection=BOOKING_STATES, string="Booking Status", compute='_compute_travel_payment',
        store=True, index=True)
    travel_cancel_date = fields.Date(string="Cancelled On", readonly=True, copy=False)
    travel_cancel_reason = fields.Char(string="Cancellation Reason", readonly=True, copy=False)
    travel_penalty_amount = fields.Monetary(string="Retained Penalty", readonly=True, copy=False)
    travel_refund_amount = fields.Monetary(string="Amount to Refund", readonly=True, copy=False)
    travel_keep_pricelist = fields.Boolean(
        string="Keep Pricelist", copy=False,
        help="Technical: the pricelist was chosen explicitly (e.g. website bookings paid in the "
             "company currency) and must not be replaced by the trip pricelist.")
    travel_document_warning = fields.Integer(
        string="Document Issues", compute='_compute_travel_document_warning')
    travel_deposit_invoiced = fields.Boolean(
        string="Deposit Invoiced", compute='_compute_travel_deposit_invoiced',
        help="Draft or posted deposit invoices already cover the deposit of the booking.")
    travel_company_currency_id = fields.Many2one(related='company_id.currency_id',
                                                 string="Company Currency")
    travel_expected_cost = fields.Monetary(
        string="Expected Supplier Cost", compute='_compute_travel_expected_cost', store=True,
        currency_field='travel_company_currency_id',
        groups='odossey_travel.group_travel_manager',
        help="Supplier cost of the services of the trip for the passengers of the booking, "
             "in the company currency.")

    @api.depends('travel_passenger_ids')
    def _compute_travel_pax(self):
        for order in self:
            order.travel_pax_count = len(order.travel_passenger_ids)

    @api.depends('trip_id.deposit_type', 'trip_id.deposit_amount', 'trip_id.deposit_percent',
                 'travel_pax_count', 'amount_total', 'currency_id')
    def _compute_travel_deposit_required(self):
        for order in self:
            trip = order.trip_id
            if order.state in ('sale', 'cancel') and order.travel_deposit_required \
                    and not order.currency_id.is_zero(order.travel_deposit_required):
                # snapshot taken when the booking was confirmed: later changes of the trip
                # deposit do not apply to confirmed bookings
                continue
            if not trip:
                order.travel_deposit_required = 0.0
            elif trip.deposit_type == 'fixed':
                amount = trip.deposit_amount * max(order.travel_pax_count, 1)
                order.travel_deposit_required = trip.currency_id._convert(
                    amount, order.currency_id, order.company_id,
                    order.date_order or fields.Date.today())
            else:
                order.travel_deposit_required = order.amount_total * trip.deposit_percent / 100.0

    @api.depends('state', 'amount_total', 'travel_deposit_required', 'trip_id',
                 'travel_penalty_amount',
                 'order_line.invoice_lines.move_id.state',
                 'order_line.invoice_lines.move_id.amount_total',
                 'order_line.invoice_lines.move_id.amount_residual',
                 'order_line.invoice_lines.price_total',
                 'transaction_ids.state', 'transaction_ids.payment_id.state',
                 'transaction_ids.payment_id.is_reconciled')
    def _compute_travel_payment(self):
        today = fields.Date.context_today(self)
        for order in self:
            paid = order._travel_get_amount_paid() if order.trip_id else 0.0
            rounding = order.currency_id.rounding or 0.01
            order.travel_amount_paid = paid
            if order.state == 'cancel':
                # what the customer still owes: the part of the penalty not paid yet
                order.travel_amount_due = max(order.travel_penalty_amount - paid, 0.0)
            else:
                order.travel_amount_due = max(order.amount_total - paid, 0.0)
            deposit_paid = (order.state == 'sale'
                            and not float_is_zero(paid, precision_rounding=rounding)
                            and float_compare(paid, order.travel_deposit_required,
                                              precision_rounding=rounding) >= 0)
            if order.state in ('draft', 'sent') or not order.trip_id:
                # back to quotation: the price is not frozen anymore
                frozen, frozen_date = False, False
            elif deposit_paid:
                frozen, frozen_date = True, order.travel_frozen_date or today
            else:
                # once frozen, the price stays frozen (credit notes, trip deposit changes and
                # cancellations do not unfreeze it: the frozen date is kept as history)
                frozen = bool(order.travel_price_frozen and order.travel_frozen_date)
                frozen_date = order.travel_frozen_date if frozen else False
            order.travel_price_frozen = frozen
            order.travel_frozen_date = frozen_date
            if not order.trip_id:
                order.travel_booking_state = False
            elif order.state == 'cancel':
                order.travel_booking_state = 'cancelled'
            elif order.state != 'sale':
                order.travel_booking_state = 'quotation'
            elif float_compare(paid, order.amount_total, precision_rounding=rounding) >= 0:
                order.travel_booking_state = 'paid'
            elif frozen:
                order.travel_booking_state = 'deposit'
            else:
                order.travel_booking_state = 'pending'

    def _travel_get_amount_paid(self):
        """Paid amount of the booking in the order currency.

        For every posted customer invoice / credit note of the order, the paid ratio of the
        move is applied to the part of the move that belongs to this order (its invoice lines
        linked to the order lines, down payment deductions included), so that an invoice
        covering several bookings is split between them."""
        self.ensure_one()
        paid = 0.0
        moves = self.order_line.invoice_lines.move_id.filtered(
            lambda m: m.state == 'posted' and m.move_type in ('out_invoice', 'out_refund'))
        for move in moves:
            if move.currency_id.is_zero(move.amount_total):
                continue
            ratio = (move.amount_total - move.amount_residual) / move.amount_total
            order_part = sum(move.invoice_line_ids.filtered(
                lambda l: l.sale_line_ids.order_id == self).mapped('price_total'))
            amount = order_part * ratio
            if move.currency_id != self.currency_id:
                amount = move.currency_id._convert(
                    amount, self.currency_id, self.company_id,
                    move.invoice_date or fields.Date.context_today(self))
            paid += -amount if move.move_type == 'out_refund' else amount
        # Online payments not reconciled with the invoices yet (e.g. payment journals without
        # outstanding account: the payment stays "in process" until the bank reconciliation).
        for tx in self.sudo().transaction_ids.filtered(
                lambda t: t.state == 'done' and t.operation != 'validation'
                and len(t.sale_order_ids) == 1 and t.payment_id
                and t.payment_id.state == 'in_process' and not t.payment_id.is_reconciled):
            amount = tx.amount
            if tx.currency_id != self.currency_id:
                amount = tx.currency_id._convert(amount, self.currency_id, self.company_id,
                                                 tx.create_date.date())
            paid += amount
        return paid

    def _travel_get_deposit_invoiced(self):
        """Amount (taxes included, order currency) of the deposit invoices of the booking that
        are not cancelled (draft or posted), credit notes deducted."""
        self.ensure_one()
        amount = 0.0
        lines = self.order_line.filtered(lambda l: l.is_downpayment and not l.display_type)
        for line in lines.invoice_lines.filtered(
                lambda l: l.move_id.state != 'cancel' and l.quantity > 0
                and l.move_id.move_type in ('out_invoice', 'out_refund')):
            value = line.price_total
            if line.currency_id != self.currency_id:
                value = line.currency_id._convert(
                    value, self.currency_id, self.company_id,
                    line.move_id.invoice_date or fields.Date.context_today(self))
            amount += -value if line.move_id.move_type == 'out_refund' else value
        return amount

    @api.depends('travel_deposit_required', 'order_line.invoice_lines.move_id.state',
                 'order_line.invoice_lines.price_total')
    def _compute_travel_deposit_invoiced(self):
        for order in self:
            order.travel_deposit_invoiced = bool(
                order.trip_id and order.travel_deposit_required
                and order.currency_id.compare_amounts(
                    order._travel_get_deposit_invoiced(), order.travel_deposit_required) >= 0)

    @api.depends('trip_id.component_ids.cost_unit', 'trip_id.component_ids.per_passenger',
                 'trip_id.currency_id', 'travel_pax_count', 'company_id', 'date_order')
    def _compute_travel_expected_cost(self):
        for order in self:
            trip = order.trip_id
            if not trip:
                order.travel_expected_cost = 0.0
                continue
            cost = sum(
                component.cost_unit * (order.travel_pax_count if component.per_passenger else 1)
                for component in trip.component_ids)
            order.travel_expected_cost = trip.currency_id._convert(
                cost, order.company_id.currency_id, order.company_id,
                order.date_order or fields.Date.context_today(self))

    @api.depends('travel_passenger_ids.document_state')
    def _compute_travel_document_warning(self):
        for order in self:
            order.travel_document_warning = len(order.travel_passenger_ids.filtered(
                lambda p: p.document_state != 'ok'))

    @api.depends('trip_id')
    def _compute_pricelist_id(self):
        super()._compute_pricelist_id()
        for order in self.filtered(
                lambda o: o.trip_id and o.state == 'draft' and not o.travel_keep_pricelist):
            pricelist = order.trip_id._get_booking_pricelist()
            if pricelist and order.pricelist_id != pricelist \
                    and (order.trip_id.pricelist_id
                         or order.pricelist_id.currency_id != order.trip_id.currency_id):
                order.pricelist_id = pricelist

    @api.onchange('trip_id')
    def _onchange_trip_id(self):
        if self.travel_group_id and self.travel_group_id.trip_id != self.trip_id:
            self.travel_group_id = False

    @api.onchange('partner_id')
    def _onchange_partner_travel_passenger(self):
        """A new booking travels with its customer by default."""
        if self.trip_id and self.partner_id and not self.travel_passenger_ids \
                and self.partner_id.type == 'contact' and not self.partner_id.is_company:
            self.travel_passenger_ids = [Command.create({'partner_id': self.partner_id.id})]

    # ------------------------------------------------------------------
    # Business
    # ------------------------------------------------------------------
    def action_travel_load_services(self):
        self._travel_load_services()

    def _travel_load_services(self):
        """(Re)build the order lines from the services of the trip, for the passengers of the
        booking. Only possible on quotations: confirmed bookings keep their frozen price."""
        for order in self.filtered('trip_id'):
            if order.state not in ('draft', 'sent'):
                raise UserError(self.env._(
                    "The services of %s cannot be reloaded: the booking is confirmed and its "
                    "price is frozen.", order.name))
            trip = order.trip_id
            pax = max(order.travel_pax_count, 1)
            dates = self.env._("from %(start)s to %(end)s",
                               start=format_date(self.env, trip.date_start),
                               end=format_date(self.env, trip.date_end))
            section_prefix = f"{trip.display_name} - "
            commands = [Command.unlink(line.id) for line in order.order_line.filtered(
                lambda l: l.travel_component_id or l.travel_section
                or (l.display_type == 'line_section' and not l.is_downpayment
                    and (l.name or '').startswith(section_prefix))
                or (not l.display_type and not l.is_downpayment and not l.product_id))]
            commands.append(Command.create({
                'display_type': 'line_section',
                'name': f"{section_prefix}{trip.destination} ({dates})",
                'travel_section': True,
            }))
            for component in trip.component_ids:
                vals = {
                    'product_id': component.product_id.id,
                    'name': component.name,
                    'product_uom_qty': pax if component.per_passenger else 1,
                    'travel_component_id': component.id,
                }
                if trip.analytic_account_id:
                    vals['analytic_distribution'] = {str(trip.analytic_account_id.id): 100}
                commands.append(Command.create(vals))
            order.order_line = commands
            order.order_line.filtered('travel_component_id')._compute_price_unit()

    def action_confirm(self):
        travel_orders = self.filtered('trip_id')
        for order in travel_orders:
            trip = order.trip_id
            if trip.state in ('done', 'cancel'):
                raise UserError(self.env._(
                    "The trip %s is %s: it cannot be booked.", trip.display_name,
                    dict(trip._fields['state']._description_selection(self.env))[trip.state]))
            if not order.travel_passenger_ids:
                raise UserError(self.env._(
                    "Add the passengers of the booking %s before confirming it.", order.name))
        travel_orders.trip_id._travel_check_seats(travel_orders)
        return super().action_confirm()

    @api.constrains('state', 'trip_id')
    def _check_travel_passenger_unique(self):
        self.filtered(lambda o: o.trip_id and o.state == 'sale') \
            .travel_passenger_ids._check_trip_partner_unique()

    def action_travel_register_deposit(self):
        """Open the standard down payment wizard with the deposit amount pre-filled."""
        self.ensure_one()
        if self.state != 'sale':
            raise UserError(self.env._(
                "Confirm the booking before invoicing the deposit."))
        already = self._travel_get_deposit_invoiced()
        amount = self.travel_deposit_required - already
        if self.currency_id.compare_amounts(amount, 0.0) <= 0:
            raise UserError(self.env._(
                "The deposit of %s is already invoiced.", self.name))
        action = self.env['ir.actions.act_window']._for_xml_id(
            'sale.action_view_sale_advance_payment_inv')
        action['context'] = {
            'active_model': 'sale.order',
            'active_ids': self.ids,
            'active_id': self.id,
            'default_advance_payment_method': 'fixed',
            'default_fixed_amount': self.currency_id.round(amount),
        }
        return action

    def action_travel_cancel_booking(self):
        self.ensure_one()
        return {
            'name': self.env._("Cancel Booking"),
            'type': 'ir.actions.act_window',
            'res_model': 'travel.booking.cancel',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_order_id': self.id},
        }

    def action_travel_scan_passenger(self):
        self.ensure_one()
        return self.env['travel.document.scan'].action_open(sale_order=self)

    def action_view_trip(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'travel.trip',
            'res_id': self.trip_id.id,
            'view_mode': 'form',
        }

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.trip_id:
            vals['trip_id'] = self.trip_id.id
            vals['travel_group_id'] = self.travel_group_id.id
            if self.company_id.travel_invoice_service_dates == 'trip':
                vals['l10n_ar_afip_service_start'] = self.trip_id.date_start
                vals['l10n_ar_afip_service_end'] = self.trip_id.date_end
        return vals

    def _get_invoice_grouping_keys(self):
        # never merge bookings of different trips or groups in the same invoice
        return super()._get_invoice_grouping_keys() + ['trip_id', 'travel_group_id']

    @api.model
    def _travel_historical_cancel_rate(self):
        """Cancelled / confirmed bookings of the completed trips of the current company."""
        domain = [('trip_id.state', '=', 'done'), ('company_id', '=', self.env.company.id),
                  ('travel_booking_state', '!=', 'quotation')]
        total = self.search_count(domain)
        cancelled = self.search_count(domain + [('travel_booking_state', '=', 'cancelled')])
        return round(100.0 * cancelled / total, 2) if total else 0.0


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    travel_component_id = fields.Many2one('travel.trip.component', string="Trip Service",
                                          index='btree_not_null', copy=True)
    travel_section = fields.Boolean(
        string="Trip Section", copy=True,
        help="Technical: section line created from the trip, replaced when the services of "
             "the trip are reloaded.")

    def _reset_price_unit(self):
        if not self.travel_component_id:
            return super()._reset_price_unit()
        component = self.travel_component_id
        price = component.currency_id._convert(
            component.price_unit, self.order_id.currency_id, self.company_id,
            self.order_id.date_order or fields.Date.today())
        self.update({'price_unit': price, 'technical_price_unit': price})
