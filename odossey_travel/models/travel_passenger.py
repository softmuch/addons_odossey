from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

BOOKING_STATES = [
    ('quotation', "Quotation"),
    ('pending', "Deposit Pending"),
    ('deposit', "Price Frozen"),
    ('paid', "Fully Paid"),
    ('cancelled', "Cancelled"),
]


class TravelPassenger(models.Model):
    _name = 'travel.passenger'
    _description = "Trip Passenger"
    _order = 'trip_id, sale_order_id, sequence, id'
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    sale_order_id = fields.Many2one('sale.order', string="Booking", required=True,
                                    ondelete='cascade', index=True)
    partner_id = fields.Many2one('res.partner', string="Passenger", required=True, index=True)
    trip_id = fields.Many2one(related='sale_order_id.trip_id', store=True, index=True,
                              string="Trip")
    group_id = fields.Many2one(related='sale_order_id.travel_group_id', store=True,
                               string="Group")
    payer_id = fields.Many2one(related='sale_order_id.partner_id', store=True, string="Payer")
    company_id = fields.Many2one(related='sale_order_id.company_id', store=True)
    state = fields.Selection(related='sale_order_id.travel_booking_state', store=True,
                             string="Booking Status")
    date_start = fields.Date(related='trip_id.date_start', string="Departure")
    date_end = fields.Date(related='trip_id.date_end', string="Return")
    passenger_type = fields.Selection(
        selection=[('adult', "Adult"), ('child', "Child"), ('infant', "Infant")],
        string="Type", default='adult', required=True)
    room_type = fields.Selection(
        selection=[
            ('single', "Single"),
            ('double', "Double"),
            ('twin', "Twin"),
            ('triple', "Triple"),
            ('quadruple', "Quadruple"),
            ('shared', "Shared (assigned)"),
        ], string="Room", default='double')
    room_number = fields.Char(string="Rooming Group",
                              help="Passengers sharing a room get the same rooming group.")
    notes = fields.Char(string="Notes")
    # Passenger data (from the contact)
    birthdate = fields.Date(related='partner_id.birthdate')
    age_at_departure = fields.Integer(string="Age at Departure",
                                      compute='_compute_age_at_departure')
    vat = fields.Char(related='partner_id.vat', string="ID Number")
    passport_number = fields.Char(related='partner_id.passport_number')
    passport_expiry_date = fields.Date(related='partner_id.passport_expiry_date')
    nationality_id = fields.Many2one(related='partner_id.nationality_id')
    phone = fields.Char(related='partner_id.phone')
    email = fields.Char(related='partner_id.email')
    document_state = fields.Selection(
        selection=[
            ('ok', "OK"),
            ('missing', "Passport Missing"),
            ('expiring', "Passport Expiring"),
            ('missing_id', "ID Missing"),
        ], string="Documents", compute='_compute_document_state', store=True,
        help="International trips require a passport valid the configured number of months "
             "after the return date. National trips require an ID number.")

    _partner_unique = models.Constraint(
        'UNIQUE(sale_order_id, partner_id)',
        "A passenger can only appear once in a booking.")

    @api.depends('birthdate', 'trip_id.date_start')
    def _compute_age_at_departure(self):
        for passenger in self:
            ref = passenger.trip_id.date_start or fields.Date.context_today(self)
            passenger.age_at_departure = (relativedelta(ref, passenger.birthdate).years
                                          if passenger.birthdate else 0)

    @api.depends('partner_id.passport_number', 'partner_id.passport_expiry_date',
                 'partner_id.vat', 'trip_id.trip_type', 'trip_id.date_end',
                 'trip_id.company_id.travel_passport_validity_months')
    def _compute_document_state(self):
        for passenger in self:
            trip = passenger.trip_id
            partner = passenger.partner_id
            if trip.trip_type == 'international':
                months = trip.company_id.travel_passport_validity_months
                if not partner.passport_number or not partner.passport_expiry_date:
                    passenger.document_state = 'missing'
                elif trip.date_end and (
                        partner.passport_expiry_date < trip.date_end + relativedelta(months=months)):
                    passenger.document_state = 'expiring'
                else:
                    passenger.document_state = 'ok'
            else:
                passenger.document_state = 'ok' if partner.vat else 'missing_id'

    def action_open_partner(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
