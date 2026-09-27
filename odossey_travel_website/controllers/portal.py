from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.sale.controllers.portal import CustomerPortal, PaymentPortal


class TravelCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'travel_booking_count' in counters:
            partner = request.env.user.partner_id
            values['travel_booking_count'] = request.env['sale.order'].search_count([
                ('trip_id', '!=', False),
                ('partner_id', 'child_of', [partner.commercial_partner_id.id]),
            ]) if request.env['sale.order'].has_access('read') else 0
        return values

    @http.route(['/my/trips'], type='http', auth='user', website=True)
    def portal_my_trips(self, **kw):
        partner = request.env.user.partner_id
        orders = request.env['sale.order'].search([
            ('trip_id', '!=', False),
            ('partner_id', 'child_of', [partner.commercial_partner_id.id]),
        ], order='travel_date_start desc, id desc')
        values = self._prepare_portal_layout_values()
        # the record rules filtered the orders of the customer: render them with sudo to read
        # the trip information (trips are not readable by portal users)
        values.update({'orders': orders.sudo(), 'page_name': 'travel_bookings'})
        return request.render('odossey_travel_website.portal_my_trips', values)


class TravelPaymentPortal(PaymentPortal):

    @http.route()
    def portal_order_transaction(self, order_id, access_token, **kwargs):
        """Re-check the seats before paying an online trip quotation."""
        order_sudo = self._document_check_access('sale.order', order_id, access_token)
        trip = order_sudo.trip_id
        if trip and order_sudo.state in ('draft', 'sent') and trip.capacity:
            trip._web_lock()
            held_by_others = trip._web_held_seats() - order_sudo.travel_pax_count
            free = trip.capacity - trip.seats_reserved - max(held_by_others, 0)
            if order_sudo.travel_pax_count > free:
                raise ValidationError(request.env._(
                    "Sorry, the trip is full: there are only %s seats left.", max(free, 0)))
        return super().portal_order_transaction(order_id, access_token, **kwargs)
