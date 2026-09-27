from datetime import datetime, time, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command, Domain


class TravelTrip(models.Model):
    _name = 'travel.trip'
    _description = "Trip"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = 'date_start desc, id desc'
    _check_company_auto = True

    name = fields.Char(string="Trip", required=True, tracking=True)
    code = fields.Char(string="Reference", readonly=True, copy=False, default='/')
    active = fields.Boolean(default=True)
    color = fields.Integer(string="Color")
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, index=True,
        default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(related='company_id.currency_id', string="Company Currency")
    currency_id = fields.Many2one(
        'res.currency', string="Currency", required=True, tracking=True,
        default=lambda self: self.env.company.currency_id,
        help="Currency in which the trip is quoted and sold (e.g. USD for international trips).")
    pricelist_id = fields.Many2one(
        'product.pricelist', string="Pricelist", check_company=True,
        domain="[('currency_id', '=', currency_id)]",
        help="Pricelist used on the bookings. It must use the trip currency.")
    user_id = fields.Many2one(
        'res.users', string="Responsible", tracking=True, default=lambda self: self.env.user,
        domain="[('share', '=', False)]")
    coordinator_id = fields.Many2one('res.partner', string="Coordinator")
    state = fields.Selection(
        selection=[
            ('draft', "Planning"),
            ('open', "On Sale"),
            ('confirmed', "Confirmed"),
            ('done', "Completed"),
            ('cancel', "Cancelled"),
        ], string="Status", default='draft', required=True, tracking=True, copy=False,
        group_expand=True)
    # Destination & dates
    destination = fields.Char(string="Destination", required=True, tracking=True)
    country_id = fields.Many2one('res.country', string="Country")
    trip_type = fields.Selection(
        selection=[('national', "National"), ('international', "International")],
        string="Type", compute='_compute_trip_type', store=True, readonly=False, required=True,
        precompute=True)
    date_start = fields.Date(string="Departure", required=True, tracking=True)
    date_end = fields.Date(string="Return", required=True, tracking=True)
    nights = fields.Integer(string="Nights", compute='_compute_nights', store=True)
    description = fields.Html(string="Description", translate=True)
    includes_flight = fields.Boolean(string="Flights")
    includes_lodging = fields.Boolean(string="Lodging")
    includes_transfer = fields.Boolean(string="Transfers")
    includes_excursions = fields.Boolean(string="Excursions")
    includes_assistance = fields.Boolean(string="Travel Assistance")
    not_included = fields.Char(string="Not Included", translate=True)
    conditions = fields.Html(
        string="Conditions", translate=True,
        default=lambda self: self.env.company.travel_quotation_conditions)
    # Capacity
    capacity = fields.Integer(string="Capacity", tracking=True,
                              help="Maximum number of passengers (0 = unlimited).")
    min_pax = fields.Integer(string="Minimum Passengers",
                             help="Minimum number of passengers for the trip to take place.")
    seats_reserved = fields.Integer(string="Booked Seats", compute='_compute_seats', store=True)
    seats_quoted = fields.Integer(string="Quoted Seats", compute='_compute_seats', store=True)
    seats_available = fields.Integer(string="Available Seats", compute='_compute_seats', store=True)
    occupancy_rate = fields.Float(string="Occupancy (%)", compute='_compute_seats', store=True,
                                  aggregator='avg')
    min_pax_reached = fields.Boolean(string="Minimum Reached", compute='_compute_seats', store=True)
    # Prices
    component_ids = fields.One2many('travel.trip.component', 'trip_id', string="Services",
                                    copy=True)
    price_per_person = fields.Monetary(
        string="Price per Person", compute='_compute_prices', store=True,
        help="Sale price per passenger (sum of the services, taxes included as defined on each "
             "service product).")
    cost_per_person = fields.Monetary(string="Cost per Person", compute='_compute_prices',
                                      store=True, groups='odossey_travel.group_travel_manager')
    cost_per_booking = fields.Monetary(
        string="Cost per Booking", compute='_compute_prices', store=True,
        groups='odossey_travel.group_travel_manager',
        help="Supplier cost of the services invoiced once per booking.")
    margin_per_person = fields.Monetary(string="Margin per Person", compute='_compute_prices',
                                        store=True, groups='odossey_travel.group_travel_manager')
    fixed_cost = fields.Monetary(
        string="Fixed Costs", groups='odossey_travel.group_travel_manager',
        help="Costs of the trip that do not depend on the number of passengers (coordinator, "
             "bus, marketing...). Used in the forecast.")
    deposit_type = fields.Selection(
        selection=[('fixed', "Fixed amount per passenger"), ('percent', "Percentage")],
        string="Deposit Type", default='percent', required=True)
    deposit_amount = fields.Monetary(string="Deposit per Passenger")
    deposit_percent = fields.Float(string="Deposit (%)", default=30.0)
    balance_due_days = fields.Integer(
        string="Balance Due (days before)", default=30,
        help="The balance must be fully paid this number of days before departure.")
    balance_due_date = fields.Date(string="Balance Due Date", compute='_compute_balance_due_date',
                                   store=True)
    quotation_validity_hours = fields.Integer(string="Quotation Validity (hours)", default=48)
    cancellation_policy_id = fields.Many2one(
        'travel.cancellation.policy', string="Cancellation Policy", check_company=True,
        default=lambda self: self.env['travel.cancellation.policy'].search(
            [('company_id', 'in', [False, self.env.company.id])], limit=1))
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string="Analytic Account", copy=False, check_company=True)
    # Relations
    sale_order_ids = fields.One2many('sale.order', 'trip_id', string="Bookings")
    passenger_ids = fields.One2many('travel.passenger', 'trip_id', string="Passengers")
    group_ids = fields.One2many('travel.group', 'trip_id', string="Groups")
    activity_line_ids = fields.One2many(
        'travel.activity', 'trip_id', string="Itinerary",
        domain=[('activity_type', '!=', 'trip')])
    lead_ids = fields.One2many('crm.lead', 'trip_id', string="Opportunities")
    order_count = fields.Integer(compute='_compute_counts', string="Bookings Count")
    lead_count = fields.Integer(compute='_compute_counts', string="Opportunities Count")
    invoice_count = fields.Integer(compute='_compute_counts', string="Invoices Count")
    group_count = fields.Integer(compute='_compute_counts', string="Groups Count")
    passenger_count = fields.Integer(compute='_compute_counts', string="Passengers Count")
    document_warning_count = fields.Integer(
        string="Document Issues", compute='_compute_counts',
        help="Passengers with missing or expiring passport for this trip.")
    # Financial summary (company currency)
    amount_booked = fields.Monetary(
        string="Booked", compute='_compute_financials', currency_field='company_currency_id')
    amount_paid = fields.Monetary(
        string="Collected", compute='_compute_financials', currency_field='company_currency_id')
    amount_due = fields.Monetary(
        string="Pending Balance", compute='_compute_financials',
        currency_field='company_currency_id')
    expected_revenue = fields.Monetary(
        string="Expected Revenue", compute='_compute_financials',
        currency_field='company_currency_id',
        groups='odossey_travel.group_travel_manager')
    expected_margin = fields.Monetary(
        string="Expected Margin", compute='_compute_financials',
        currency_field='company_currency_id',
        groups='odossey_travel.group_travel_manager')
    # Net profitability (company currency, posted accounting entries, managers only)
    profit_gross = fields.Monetary(
        string="Gross Invoiced", compute='_compute_profitability',
        currency_field='company_currency_id', groups='odossey_travel.group_travel_manager')
    profit_vat = fields.Monetary(
        string="VAT", compute='_compute_profitability',
        currency_field='company_currency_id', groups='odossey_travel.group_travel_manager')
    profit_perception = fields.Monetary(
        string="Perceptions", compute='_compute_profitability',
        currency_field='company_currency_id', groups='odossey_travel.group_travel_manager')
    profit_other_tax = fields.Monetary(
        string="Other Taxes", compute='_compute_profitability',
        currency_field='company_currency_id', groups='odossey_travel.group_travel_manager')
    profit_revenue = fields.Monetary(
        string="Net Revenue", compute='_compute_profitability',
        currency_field='company_currency_id', groups='odossey_travel.group_travel_manager')
    profit_cost = fields.Monetary(
        string="Supplier Costs", compute='_compute_profitability',
        currency_field='company_currency_id', groups='odossey_travel.group_travel_manager')
    profit_fee = fields.Monetary(
        string="Fees", compute='_compute_profitability',
        currency_field='company_currency_id', groups='odossey_travel.group_travel_manager')
    profit_iibb = fields.Monetary(
        string="Gross Income Tax (IIBB)", compute='_compute_profitability',
        currency_field='company_currency_id', groups='odossey_travel.group_travel_manager')
    profit_net = fields.Monetary(
        string="Net Profit", compute='_compute_profitability',
        currency_field='company_currency_id', groups='odossey_travel.group_travel_manager')
    profit_margin = fields.Float(string="Net Margin (%)", compute='_compute_profitability',
                                 groups='odossey_travel.group_travel_manager')

    _dates_check = models.Constraint(
        'CHECK(date_end >= date_start)', "The return date must be after the departure date.")

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('country_id', 'company_id')
    def _compute_trip_type(self):
        for trip in self:
            company_country = trip.company_id.country_id or self.env.company.country_id
            trip.trip_type = ('international' if trip.country_id and company_country
                              and trip.country_id != company_country else 'national')

    @api.depends('date_start', 'date_end')
    def _compute_nights(self):
        for trip in self:
            trip.nights = ((trip.date_end - trip.date_start).days
                           if trip.date_start and trip.date_end else 0)

    @api.depends('date_start', 'balance_due_days')
    def _compute_balance_due_date(self):
        for trip in self:
            trip.balance_due_date = (trip.date_start - timedelta(days=trip.balance_due_days)
                                     if trip.date_start else False)

    @api.depends('component_ids.price_unit', 'component_ids.cost_unit',
                 'component_ids.per_passenger')
    def _compute_prices(self):
        for trip in self:
            components = trip.component_ids.filtered('per_passenger')
            trip.price_per_person = sum(components.mapped('price_unit'))
            trip.cost_per_person = sum(components.mapped('cost_unit'))
            trip.cost_per_booking = sum((trip.component_ids - components).mapped('cost_unit'))
            trip.margin_per_person = trip.price_per_person - trip.cost_per_person

    @api.depends('capacity', 'min_pax', 'passenger_ids.state')
    def _compute_seats(self):
        for trip in self:
            states = trip.passenger_ids.mapped('state')
            trip.seats_reserved = len([s for s in states if s in ('pending', 'deposit', 'paid')])
            trip.seats_quoted = len([s for s in states if s == 'quotation'])
            trip.seats_available = (max(trip.capacity - trip.seats_reserved, 0)
                                    if trip.capacity else 0)
            trip.occupancy_rate = (100.0 * trip.seats_reserved / trip.capacity
                                   if trip.capacity else 0.0)
            trip.min_pax_reached = trip.seats_reserved >= trip.min_pax

    def _compute_counts(self):
        domain = [('trip_id', 'in', self.ids)]

        def count(model):
            return {trip.id: cnt for trip, cnt in model._read_group(
                domain, ['trip_id'], ['__count'])}

        orders = count(self.env['sale.order'])
        leads = count(self.env['crm.lead'].with_context(active_test=False))
        invoices = count(self.env['account.move'])
        groups = count(self.env['travel.group'])
        passengers, warnings = {}, {}
        for trip, document_state, cnt in self.env['travel.passenger']._read_group(
                domain + [('state', '!=', 'cancelled')], ['trip_id', 'document_state'],
                ['__count']):
            passengers[trip.id] = passengers.get(trip.id, 0) + cnt
            if document_state != 'ok':
                warnings[trip.id] = warnings.get(trip.id, 0) + cnt
        for trip in self:
            trip.order_count = orders.get(trip.id, 0)
            trip.lead_count = leads.get(trip.id, 0)
            trip.invoice_count = invoices.get(trip.id, 0)
            trip.group_count = groups.get(trip.id, 0)
            trip.passenger_count = passengers.get(trip.id, 0)
            trip.document_warning_count = warnings.get(trip.id, 0)

    def _compute_financials(self):
        # the forecast is restricted to the managers, but the amounts booked / collected of
        # the trip are shown to every travel user
        Forecast = self.env['travel.forecast.report'].sudo()
        data = {
            trip.id: (booked, paid, due, revenue, margin)
            for trip, booked, paid, due, revenue, margin in Forecast._read_group(
                [('trip_id', 'in', self.ids), ('booking_state', '!=', 'quotation')],
                ['trip_id'],
                ['amount_total:sum', 'amount_paid:sum', 'amount_due:sum',
                 'expected_revenue:sum', 'expected_margin:sum'])
        }
        forecast_all = {
            trip.id: (revenue, margin)
            for trip, revenue, margin in Forecast._read_group(
                [('trip_id', 'in', self.ids)], ['trip_id'],
                ['expected_revenue:sum', 'expected_margin:sum'])
        }
        for trip in self:
            booked, paid, due, __, __ = data.get(trip.id, (0.0,) * 5)
            revenue, margin = forecast_all.get(trip.id, (0.0, 0.0))
            trip.amount_booked = booked
            trip.amount_paid = paid
            trip.amount_due = due
            trip.expected_revenue = revenue
            fixed_cost = trip.sudo().fixed_cost
            trip.expected_margin = margin - trip.currency_id._convert(
                fixed_cost, trip.company_currency_id, trip.company_id,
                trip.date_start or fields.Date.today()) if fixed_cost else margin

    def _compute_profitability(self):
        values = self._travel_profitability_values()
        for trip in self:
            vals = values.get(trip.id, {})
            for key in ('gross', 'vat', 'perception', 'other_tax', 'revenue', 'cost', 'fee',
                        'iibb', 'net'):
                trip[f'profit_{key}'] = vals.get(key, 0.0)
            trip.profit_margin = (100.0 * vals['net'] / vals['revenue']
                                  if vals.get('revenue') else 0.0)

    def _travel_profitability_values(self):
        """Return {trip_id: {measure: amount}} from the profitability report."""
        measures = ['gross', 'vat', 'perception', 'other_tax', 'revenue', 'cost', 'fee', 'iibb',
                    'net']
        rows = self.env['travel.profitability.report'].sudo()._read_group(
            [('trip_id', 'in', self.ids)], ['trip_id'],
            [f'{m}_amount:sum' for m in measures])
        return {row[0].id: dict(zip(measures, row[1:])) for row in rows}

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', '/') == '/':
                vals['code'] = self.env['ir.sequence'].next_by_code('travel.trip') or '/'
        trips = super().create(vals_list)
        trips._sync_calendar_activity()
        return trips

    def write(self, vals):
        res = super().write(vals)
        if {'name', 'destination', 'date_start', 'date_end', 'user_id', 'active',
                'company_id', 'state'} & set(vals):
            self._sync_calendar_activity()
        return res

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for trip in self:
            trip.display_name = (f"[{trip.code}] {trip.name}" if trip.code and trip.code != '/'
                                 else trip.name)

    @api.constrains('capacity', 'min_pax')
    def _check_capacity(self):
        for trip in self:
            if trip.capacity < 0 or trip.min_pax < 0:
                raise ValidationError(self.env._("Capacity values cannot be negative."))
            if trip.capacity and trip.min_pax > trip.capacity:
                raise ValidationError(self.env._(
                    "The minimum number of passengers cannot exceed the capacity."))

    def _sync_calendar_activity(self):
        """Every trip has one calendar entry spanning the whole trip, shown in the main
        calendar together with the itinerary activities of the passengers."""
        Activity = self.env['travel.activity'].sudo().with_context(active_test=False,
                                                                   travel_sync=True)
        existing = {a.trip_id.id: a for a in Activity.search(
            [('trip_id', 'in', self.ids), ('activity_type', '=', 'trip')])}
        to_create = []
        for trip in self:
            vals = {
                'name': trip.name,
                'location': trip.destination,
                'start': datetime.combine(trip.date_start, time(0, 0)),
                'stop': datetime.combine(trip.date_end, time(23, 59)),
                'allday': True,
                'user_id': trip.user_id.id,
                # a cancelled trip leaves the calendar (archived), it is restored with it
                'active': trip.active and trip.state != 'cancel',
                'company_id': trip.company_id.id,
            }
            if trip.id in existing:
                existing[trip.id].write(vals)
            else:
                to_create.append(dict(vals, trip_id=trip.id, activity_type='trip',
                                      all_passengers=True))
        if to_create:
            Activity.create(to_create)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _travel_check_seats(self, orders=None):
        """Raise if the confirmed passengers of the trips plus the passengers of ``orders``
        (bookings being confirmed or modified) exceed the capacity. The trips are locked
        until the end of the transaction so that concurrent confirmations cannot overbook
        them."""
        orders = orders or self.env['sale.order']
        trips = self.filtered('capacity')
        if not trips:
            return
        self.env.cr.execute("SELECT id FROM travel_trip WHERE id IN %s FOR UPDATE",
                            [tuple(trips.ids)])
        self.env['travel.passenger'].flush_model()
        Passenger = self.env['travel.passenger'].sudo()
        for trip in trips:
            trip_orders = orders.filtered(lambda o: o.trip_id == trip)
            booked = Passenger.search_count([
                ('trip_id', '=', trip.id),
                ('state', 'in', ('pending', 'deposit', 'paid')),
                ('sale_order_id', 'not in', trip_orders.ids),
            ])
            requested = sum(trip_orders.mapped('travel_pax_count'))
            if booked + requested > trip.capacity:
                raise UserError(self.env._(
                    "Not enough seats left on %(trip)s: %(free)s available, %(pax)s "
                    "requested.", trip=trip.display_name,
                    free=max(trip.capacity - booked, 0), pax=requested))

    def action_open(self):
        self._ensure_analytic_account()
        self.write({'state': 'open'})

    def action_confirm(self):
        self._ensure_analytic_account()
        self.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def _ensure_analytic_account(self):
        plan = self.env['account.analytic.plan'].sudo().search(
            [('name', '=', 'Travel')], limit=1)
        if not plan:
            plan = self.env['account.analytic.plan'].sudo().create({'name': 'Travel'})
        for trip in self.filtered(lambda t: not t.analytic_account_id):
            trip.analytic_account_id = self.env['account.analytic.account'].sudo().create({
                'name': trip.display_name,
                'plan_id': plan.id,
                'company_id': trip.company_id.id,
            })

    def action_new_booking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'context': {'default_trip_id': self.id},
            'target': 'current',
        }

    def action_view_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_travel.travel_booking_action')
        action['domain'] = [('trip_id', '=', self.id)]
        action['context'] = {'default_trip_id': self.id}
        return action

    def action_view_passengers(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_travel.travel_passenger_action')
        action['domain'] = [('trip_id', '=', self.id)]
        action['context'] = {'search_default_not_cancelled': 1}
        return action

    def action_view_document_warnings(self):
        action = self.action_view_passengers()
        action['context'] = {'search_default_not_cancelled': 1,
                             'search_default_document_issues': 1}
        return action

    def action_view_groups(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_travel.travel_group_action')
        action['domain'] = [('trip_id', '=', self.id)]
        action['context'] = {'default_trip_id': self.id}
        return action

    def action_view_leads(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_travel.travel_crm_lead_action')
        action['domain'] = [('trip_id', '=', self.id)]
        action['context'] = {'default_trip_id': self.id, 'default_type': 'opportunity'}
        return action

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_travel.travel_invoice_action')
        action['domain'] = [('trip_id', '=', self.id)]
        action['context'] = {'default_trip_id': self.id, 'search_default_group_by_group': 1}
        return action

    def action_view_calendar(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_travel.travel_activity_action')
        action['domain'] = [('trip_id', '=', self.id)]
        action['context'] = {'default_trip_id': self.id,
                             'initial_date': fields.Date.to_string(self.date_start)}
        return action

    def action_view_profitability(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_travel.travel_profitability_report_action')
        action['domain'] = [('trip_id', 'in', self.ids)]
        return action

    def action_update_quotation_prices(self):
        """Apply the current trip prices to open quotations whose price is not frozen."""
        orders = self.sale_order_ids.filtered(lambda o: o.state in ('draft', 'sent'))
        orders._travel_load_services()
        if not orders:
            raise UserError(self.env._("There are no open quotations to update."))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._("%s quotation(s) updated with the current prices.",
                                      len(orders)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    @api.model
    def _travel_enable_pricelists(self):
        """Enable the pricelists of Sales (Settings > Pricelists) for all the internal users."""
        group = self.env.ref('product.group_product_pricelist', raise_if_not_found=False)
        user_group = self.env.ref('base.group_user')
        if group and group not in user_group.implied_ids:
            user_group.sudo().write({'implied_ids': [Command.link(group.id)]})

    def _get_booking_pricelist(self):
        """Pricelist of the bookings: the one of the trip or a pricelist in the trip currency
        (created if needed) so that the booking is sold in the currency of the trip."""
        self.ensure_one()
        if self.pricelist_id:
            return self.pricelist_id
        Pricelist = self.env['product.pricelist'].sudo()
        pricelist = Pricelist.search([
            ('currency_id', '=', self.currency_id.id),
            ('company_id', 'in', [False, self.company_id.id]),
        ], limit=1)
        if not pricelist:
            self._travel_enable_pricelists()
            pricelist = Pricelist.create({
                'name': self.env._("Travel %s", self.currency_id.name),
                'currency_id': self.currency_id.id,
                'company_id': self.company_id.id,
            })
        return pricelist.sudo(False)

    def _get_deposit_per_passenger(self):
        self.ensure_one()
        if self.deposit_type == 'fixed':
            return self.deposit_amount
        return self.price_per_person * self.deposit_percent / 100.0


class TravelTripComponent(models.Model):
    _name = 'travel.trip.component'
    _description = "Trip Service"
    _order = 'sequence, id'

    trip_id = fields.Many2one('travel.trip', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product', string="Service", required=True,
        domain="[('sale_ok', '=', True), ('type', '=', 'service')]")
    name = fields.Char(string="Description", compute='_compute_name', store=True,
                       readonly=False, precompute=True)
    service_type = fields.Selection(related='product_id.travel_service_type')
    supplier_id = fields.Many2one('res.partner', string="Supplier")
    currency_id = fields.Many2one(related='trip_id.currency_id')
    price_unit = fields.Monetary(string="Sale Price", help="Sale price per passenger.")
    cost_unit = fields.Monetary(string="Cost", help="Supplier cost per passenger.",
                                groups='odossey_travel.group_travel_manager')
    tax_ids = fields.Many2many(related='product_id.taxes_id', string="Taxes")
    per_passenger = fields.Boolean(
        string="Per Passenger", default=True,
        help="If unchecked, the service is invoiced once per booking.")

    @api.depends('product_id')
    def _compute_name(self):
        for component in self:
            if component.product_id and not component.name:
                component.name = component.product_id.display_name

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.lst_price
            if self.env.user.has_group('odossey_travel.group_travel_manager'):
                self.cost_unit = self.product_id.standard_price
