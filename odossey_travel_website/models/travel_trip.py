import math
from datetime import timedelta

from odoo import api, fields, models
from odoo.fields import Command


class TravelTrip(models.Model):
    _name = 'travel.trip'
    _inherit = ['travel.trip', 'website.published.mixin', 'website.seo.metadata']

    website_description = fields.Html(
        string="Website Description", translate=True, sanitize_overridable=True,
        help="Content of the trip page on the website. The trip description is used if empty.")
    web_allow_deposit = fields.Boolean(
        string="Online Deposit", default=True,
        help="Website customers can pay only the deposit (it freezes the price) and the balance "
             "later. If unchecked, the full amount must be paid online.")
    web_currency = fields.Selection(
        selection=[('company', "Company currency"), ('trip', "Trip currency")],
        string="Online Payment Currency", default='company', required=True,
        help="Currency of the website bookings. Most Argentinian payment providers (e.g. Mercado "
             "Pago) only accept pesos: the price is converted at the rate of the booking day and "
             "frozen with the deposit.")
    web_max_pax = fields.Integer(string="Max Passengers per Online Booking", default=8)
    web_seats_available = fields.Integer(
        string="Seats Available Online", compute='_compute_web_seats_available',
        help="Seats left minus the seats held by the website quotations still valid.")
    web_bookable = fields.Boolean(string="Bookable Online", compute='_compute_web_bookable')

    @api.depends('name')
    def _compute_website_url(self):
        for trip in self:
            trip.website_url = (f"/viajes/{self.env['ir.http']._slug(trip)}"
                                if trip.id else '#')

    def _web_held_seats(self):
        """Seats held by website quotations that can still be paid."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        orders = self.env['sale.order'].sudo().search([
            ('trip_id', '=', self.id),
            ('travel_web_booking', '=', True),
            ('state', 'in', ('draft', 'sent')),
            '|', ('validity_date', '=', False), ('validity_date', '>=', today),
        ])
        return sum(orders.mapped('travel_pax_count'))

    @api.depends('capacity', 'seats_reserved')
    def _compute_web_seats_available(self):
        for trip in self:
            if not trip.capacity:
                trip.web_seats_available = trip.web_max_pax or 99
            else:
                trip.web_seats_available = max(
                    trip.capacity - trip.seats_reserved - trip._web_held_seats(), 0)

    @api.depends('is_published', 'state', 'date_start', 'web_seats_available')
    def _compute_web_bookable(self):
        today = fields.Date.context_today(self)
        for trip in self:
            trip.web_bookable = bool(
                trip.is_published and trip.state in ('open', 'confirmed')
                and trip.date_start and trip.date_start > today
                and trip.web_seats_available > 0 and trip.component_ids)

    def _web_lock(self):
        """Lock the trip row to serialize seat checks of concurrent online bookings."""
        self.env.cr.execute("SELECT id FROM travel_trip WHERE id IN %s FOR UPDATE",
                            [tuple(self.ids)])

    def _web_get_pricelist(self):
        self.ensure_one()
        if self.web_currency == 'trip':
            # sudo: read by the public user (the website pages are rendered for visitors)
            return self._get_booking_pricelist().sudo()
        company_currency = self.company_id.currency_id
        Pricelist = self.env['product.pricelist'].sudo()
        pricelist = Pricelist.search([
            ('currency_id', '=', company_currency.id),
            ('company_id', 'in', [False, self.company_id.id]),
        ], limit=1)
        if not pricelist:
            self._travel_enable_pricelists()
            pricelist = Pricelist.create({
                'name': self.env._("Travel %s", company_currency.name),
                'currency_id': company_currency.id,
                'company_id': self.company_id.id,
            })
        return pricelist

    def _web_price_values(self):
        """Prices shown on the website, in the online payment currency."""
        self.ensure_one()
        pricelist = self._web_get_pricelist()
        currency = pricelist.currency_id
        today = fields.Date.context_today(self)

        def convert(amount):
            return self.currency_id._convert(amount, currency, self.company_id, today)

        price = convert(self.price_per_person)
        deposit = convert(self._get_deposit_per_passenger())
        return {
            'currency': currency,
            'price': price,
            'deposit': deposit if self.web_allow_deposit and self._web_deposit_allowed() else 0.0,
            'trip_price': self.price_per_person,
            'converted': currency != self.currency_id,
        }

    def _web_deposit_allowed(self):
        """The deposit is only possible before the balance due date."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        return bool(self.web_allow_deposit and self.balance_due_date
                    and self.balance_due_date > today)

    def _web_create_booking(self, holder, passengers, room_type='double', notes=False):
        """Create the website quotation of the trip for `holder` and `passengers` (partners),
        payable online: the deposit (freezes the price) or the full amount."""
        self.ensure_one()
        validity_days = max(1, math.ceil((self.quotation_validity_hours or 48) / 24.0))
        order = self.env['sale.order'].with_company(self.company_id).create({
            'partner_id': holder.id,
            'company_id': self.company_id.id,
            'trip_id': self.id,
            'pricelist_id': self._web_get_pricelist().id,
            'travel_keep_pricelist': True,
            'travel_web_booking': True,
            'origin': self.env._("Website"),
            'require_payment': True,
            'require_signature': False,
            'validity_date': fields.Date.context_today(self) + timedelta(days=validity_days),
            'note': notes or False,
            'travel_passenger_ids': [
                Command.create({'partner_id': p.id, 'room_type': room_type, 'sequence': i})
                for i, p in enumerate(passengers)
            ],
        })
        order._travel_load_services()
        if self._web_deposit_allowed() and order.amount_total:
            percent = min(order.travel_deposit_required / order.amount_total, 1.0)
            order.prepayment_percent = percent if percent > 0 else 1.0
        else:
            order.prepayment_percent = 1.0
        order._portal_ensure_token()
        order.message_subscribe(partner_ids=holder.ids)
        order.message_post(body=self.env._("Booking created online by %s.", holder.name))
        return order

    def action_view_website(self):
        self.ensure_one()
        return self.open_website_url()
