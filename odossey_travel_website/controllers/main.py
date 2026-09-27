from datetime import timedelta

from werkzeug.exceptions import NotFound

from odoo import fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools import email_normalize


class TravelWebsite(http.Controller):
    _trips_per_page = 12

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _trip_domain(self, search=None, month=None, trip_type=None):
        website = request.website
        domain = [
            ('is_published', '=', True),
            ('state', 'in', ('open', 'confirmed')),
            ('date_start', '>', fields.Date.context_today(request.env.user)),
            ('company_id', '=', website.company_id.id),
        ]
        if search:
            domain += ['|', '|', ('name', 'ilike', search), ('destination', 'ilike', search),
                       ('country_id.name', 'ilike', search)]
        if month:
            try:
                year, mon = (int(x) for x in month.split('-'))
                start = fields.Date.to_date(f'{year:04d}-{mon:02d}-01')
                end = (start + timedelta(days=32)).replace(day=1)
                domain += [('date_start', '>=', start), ('date_start', '<', end)]
            except ValueError:
                pass
        if trip_type in ('national', 'international'):
            domain.append(('trip_type', '=', trip_type))
        return domain

    def _get_trip(self, trip_slug):
        __, trip_id = request.env['ir.http']._unslug(trip_slug)
        trip = request.env['travel.trip'].sudo().browse(trip_id or 0)
        if not trip.exists() or not trip.is_published or trip.company_id != request.website.company_id:
            raise NotFound()
        return trip

    # ------------------------------------------------------------------
    # Catalogue
    # ------------------------------------------------------------------
    @http.route(['/viajes', '/viajes/page/<int:page>'], type='http', auth='public', website=True,
                sitemap=True)
    def trips(self, page=1, search=None, month=None, trip_type=None, **kw):
        Trip = request.env['travel.trip'].sudo()
        domain = self._trip_domain(search, month, trip_type)
        total = Trip.search_count(domain)
        pager = request.website.pager(
            url='/viajes', total=total, page=page, step=self._trips_per_page,
            url_args={'search': search, 'month': month, 'trip_type': trip_type})
        trips = Trip.search(domain, order='date_start, id', limit=self._trips_per_page,
                            offset=pager['offset'])
        months = sorted({t.date_start.strftime('%Y-%m') for t in Trip.search(self._trip_domain())})
        return request.render('odossey_travel_website.trips_page', {
            'trips': trips,
            'pager': pager,
            'search': search or '',
            'month': month or '',
            'trip_type': trip_type or '',
            'months': months,
        })

    @http.route(['/viajes/<string:trip>'], type='http', auth='public',
                website=True, sitemap=True)
    def trip_page(self, trip, **kw):
        trip = self._get_trip(trip)
        return request.render('odossey_travel_website.trip_page', {
            'trip': trip,
            'main_object': trip,
            'prices': trip._web_price_values(),
            'itinerary': trip.activity_line_ids.sorted('start'),
        })

    # ------------------------------------------------------------------
    # Booking
    # ------------------------------------------------------------------
    def _booking_values(self, trip, pax, post=None, error=None):
        user = request.env.user
        partner = user.partner_id if not user._is_public() else request.env['res.partner']
        pax = max(1, min(pax, trip.web_max_pax or 1, trip.web_seats_available or 1))
        return {
            'trip': trip,
            'main_object': trip,
            'pax': pax,
            'max_pax': max(1, min(trip.web_max_pax or 1, trip.web_seats_available or 1)),
            'prices': trip._web_price_values(),
            'partner': partner,
            'post': post or {},
            'error': error,
            'id_types': request.env['l10n_latam.identification.type'].sudo().search([
                '|', ('country_id', '=', False), ('country_id.code', '=', 'AR'),
                ('active', '=', True)]),
            'responsibilities': request.env['l10n_ar.afip.responsibility.type'].sudo().search(
                [('code', 'in', ['1', '4', '5', '6'])]),
            'room_types': request.env['travel.passenger']._fields['room_type']._description_selection(
                request.env),
        }

    @http.route(['/viajes/<string:trip>/reservar'], type='http', auth='public',
                website=True, methods=['GET'], sitemap=False)
    def trip_booking_form(self, trip, pax=1, **kw):
        trip = self._get_trip(trip)
        if not trip.web_bookable:
            return request.redirect(trip.website_url)
        try:
            pax = int(pax)
        except (TypeError, ValueError):
            pax = 1
        return request.render('odossey_travel_website.trip_booking_page',
                              self._booking_values(trip, pax))

    @http.route(['/viajes/<string:trip>/reservar'], type='http', auth='public',
                website=True, methods=['POST'], sitemap=False)
    def trip_booking_submit(self, trip, **post):
        trip = self._get_trip(trip)
        try:
            pax = int(post.get('pax') or 1)
        except ValueError:
            pax = 1
        try:
            order = self._create_booking(trip, pax, post)
        except (UserError, ValidationError) as error:
            values = self._booking_values(trip, pax, post=post, error=str(error))
            return request.render('odossey_travel_website.trip_booking_page', values)
        return request.redirect(order.get_portal_url(query_string='&allow_payment=yes'))

    def _get_booking_partner(self, post):
        """Holder of the booking: the logged-in customer or a contact created from the form."""
        env = request.env
        user = env.user
        values = {
            'name': (post.get('name') or '').strip(),
            'email': email_normalize(post.get('email') or '') or False,
            'phone': (post.get('phone') or '').strip() or False,
            'vat': (post.get('vat') or '').strip().replace('-', '').replace('.', '') or False,
        }
        if post.get('id_type_id'):
            values['l10n_latam_identification_type_id'] = int(post['id_type_id'])
        if post.get('responsibility_id'):
            values['l10n_ar_afip_responsibility_type_id'] = int(post['responsibility_id'])
        if not values['name'] or not values['email']:
            raise UserError(env._("Please enter the name and a valid email of the holder."))
        if not values['vat']:
            raise UserError(env._("Please enter the identification number of the holder."))
        values.setdefault('l10n_ar_afip_responsibility_type_id', env.ref('l10n_ar.res_CF').id)
        values.setdefault('l10n_latam_identification_type_id', env.ref('l10n_ar.it_dni').id)
        Partner = env['res.partner'].sudo()
        if not user._is_public():
            partner = user.partner_id.sudo()
            partner.write({k: v for k, v in values.items() if v and not partner[k]})
            return partner
        partner = Partner.search([('vat', '=', values['vat']), ('email', '=ilike', values['email'])],
                                 limit=1)
        if partner:
            return partner
        values.update({
            'country_id': env.ref('base.ar').id,
            'lang': request.lang.code,
            'company_id': False,
        })
        return Partner.create(values)

    def _get_passenger_partner(self, index, post, holder):
        env = request.env
        name = (post.get(f'passenger_{index}_name') or '').strip()
        doc = (post.get(f'passenger_{index}_vat') or '').strip().replace('.', '') or False
        birthdate = post.get(f'passenger_{index}_birthdate') or False
        if index == 0 and post.get('holder_travels'):
            partner = holder
        elif not name:
            raise UserError(env._("Please enter the full name of passenger %s.", index + 1))
        else:
            Partner = env['res.partner'].sudo()
            partner = doc and Partner.search([('vat', '=', doc), ('is_company', '=', False)],
                                             limit=1)
            if not partner:
                partner = Partner.create({
                    'name': name,
                    'vat': doc,
                    'l10n_latam_identification_type_id': env.ref('l10n_ar.it_dni').id,
                    'l10n_ar_afip_responsibility_type_id': env.ref('l10n_ar.res_CF').id,
                    'parent_id': False,
                    'country_id': env.ref('base.ar').id,
                    'company_id': False,
                })
        if birthdate and not partner.birthdate:
            partner.birthdate = fields.Date.to_date(birthdate)
        return partner

    def _create_booking(self, trip, pax, post):
        env = request.env
        if not post.get('accept_conditions'):
            raise UserError(env._("You must accept the booking conditions and the cancellation "
                                  "policy."))
        if pax < 1 or pax > (trip.web_max_pax or 1):
            raise UserError(env._("Invalid number of passengers."))
        trip._web_lock()
        trip.invalidate_recordset(['seats_reserved'])
        if not trip.web_bookable or pax > trip.web_seats_available:
            raise UserError(env._("Sorry, there are only %s seats left on this trip.",
                                  trip.web_seats_available))
        holder = self._get_booking_partner(post)
        room_type = post.get('room_type') or 'double'
        passengers = [self._get_passenger_partner(i, post, holder) for i in range(pax)]
        if len({p.id for p in passengers}) != len(passengers):
            raise UserError(env._("The same person cannot be booked twice."))
        return trip.sudo()._web_create_booking(holder, passengers, room_type=room_type,
                                               notes=post.get('notes'))

    # ------------------------------------------------------------------
    # Withdrawal button (botón de arrepentimiento)
    # ------------------------------------------------------------------
    @http.route(['/viajes/arrepentimiento'], type='http', auth='public', website=True,
                methods=['GET', 'POST'], sitemap=True)
    def withdrawal(self, **post):
        values = {'post': post, 'done': False, 'error': False}
        if request.httprequest.method == 'POST':
            env = request.env
            order = env['sale.order'].sudo().search([
                ('name', '=', (post.get('reference') or '').strip()),
                ('trip_id', '!=', False),
            ], limit=1)
            email = email_normalize(post.get('email') or '')
            if not order or not email or email_normalize(order.partner_id.email or '') != email:
                values['error'] = env._("We could not find a booking with this reference and "
                                        "email.")
            else:
                order.travel_withdrawal_date = fields.Datetime.now()
                order.message_post(body=env._(
                    "Withdrawal requested by the customer from the website (botón de "
                    "arrepentimiento). Reason: %s", post.get('reason') or '-'))
                order.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=env._("Withdrawal request (arrepentimiento)"),
                    note=post.get('reason') or '',
                    user_id=(order.trip_id.user_id or order.user_id or env.ref('base.user_admin')).id,
                )
                values.update({'done': True, 'code': f"ARR-{order.id:06d}"})
        return request.render('odossey_travel_website.withdrawal_page', values)
