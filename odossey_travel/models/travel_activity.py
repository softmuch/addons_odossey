from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class TravelActivity(models.Model):
    """Calendar entry of the travel app: the trip itself (one entry per trip, kept in sync
    automatically) and the itinerary activities of its passengers (flights, lodging,
    transfers, excursions, meetings, document deadlines...)."""
    _name = 'travel.activity'
    _description = "Trip Activity"
    _order = 'start, id'
    _check_company_auto = True

    name = fields.Char(string="Activity", required=True)
    active = fields.Boolean(default=True)
    trip_id = fields.Many2one('travel.trip', string="Trip", required=True, ondelete='cascade',
                              index=True, check_company=True)
    company_id = fields.Many2one(related='trip_id.company_id', store=True, index=True)
    activity_type = fields.Selection(
        selection=[
            ('trip', "Trip"),
            ('flight', "Flight"),
            ('lodging', "Lodging"),
            ('transfer', "Transfer"),
            ('excursion', "Excursion"),
            ('meeting', "Meeting"),
            ('document', "Documents"),
            ('payment', "Payment Deadline"),
            ('other', "Other"),
        ], string="Type", required=True, default='excursion')
    start = fields.Datetime(string="Start", required=True)
    stop = fields.Datetime(string="End", required=True)
    allday = fields.Boolean(string="All Day")
    duration = fields.Float(string="Duration (hours)", compute='_compute_duration')
    location = fields.Char(string="Location")
    user_id = fields.Many2one('res.users', string="Responsible")
    supplier_id = fields.Many2one('res.partner', string="Supplier")
    all_passengers = fields.Boolean(
        string="All Passengers", default=True,
        help="The activity concerns every passenger of the trip.")
    partner_ids = fields.Many2many(
        'res.partner', 'travel_activity_partner_rel', 'activity_id', 'partner_id',
        string="Passengers", help="Passengers concerned when not all passengers take part.")
    passenger_partner_ids = fields.Many2many(
        'res.partner', 'travel_activity_passenger_rel', 'activity_id', 'partner_id',
        string="Participants", compute='_compute_passenger_partner_ids', store=True)
    participant_count = fields.Integer(compute='_compute_passenger_partner_ids', store=True,
                                       string="Participants Count")
    # Flight details
    carrier = fields.Char(string="Airline / Carrier")
    flight_number = fields.Char(string="Flight Number")
    route = fields.Char(string="Route", help="e.g. COR - PTY - POP")
    stops = fields.Char(string="Stops")
    baggage = fields.Char(string="Baggage")
    # Lodging details
    hotel_stars = fields.Selection(
        selection=[('1', "★"), ('2', "★★"), ('3', "★★★"), ('4', "★★★★"), ('5', "★★★★★")],
        string="Category")
    board_basis = fields.Selection(
        selection=[
            ('room_only', "Room Only"),
            ('breakfast', "Bed & Breakfast"),
            ('half_board', "Half Board"),
            ('full_board', "Full Board"),
            ('all_inclusive', "All Inclusive"),
        ], string="Board Basis")
    note = fields.Html(string="Notes")
    is_trip = fields.Boolean(compute='_compute_is_trip')

    @api.depends('start', 'stop')
    def _compute_duration(self):
        for activity in self:
            activity.duration = ((activity.stop - activity.start).total_seconds() / 3600.0
                                 if activity.start and activity.stop else 0.0)

    @api.depends('activity_type')
    def _compute_is_trip(self):
        for activity in self:
            activity.is_trip = activity.activity_type == 'trip'

    @api.depends('all_passengers', 'partner_ids', 'trip_id.passenger_ids.partner_id',
                 'trip_id.passenger_ids.state')
    def _compute_passenger_partner_ids(self):
        for activity in self:
            if activity.all_passengers:
                partners = activity.trip_id.passenger_ids.filtered(
                    lambda p: p.state != 'cancelled').partner_id
            else:
                partners = activity.partner_ids
            activity.passenger_partner_ids = partners
            activity.participant_count = len(partners)

    @api.onchange('start', 'allday')
    def _onchange_start(self):
        if self.start and (not self.stop or self.stop < self.start):
            self.stop = self.start + timedelta(hours=2)

    @api.constrains('start', 'stop')
    def _check_dates(self):
        for activity in self:
            if activity.stop < activity.start:
                raise ValidationError(self.env._("The end must be after the start."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('activity_type') == 'trip':
                self._travel_check_trip_entry_sync()
            if vals.get('stop') is None and vals.get('start'):
                vals['stop'] = fields.Datetime.to_datetime(vals['start']) + timedelta(hours=2)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('activity_type') == 'trip' or self.filtered('is_trip'):
            self._travel_check_trip_entry_sync()
        return super().write(vals)

    def unlink(self):
        if self.filtered('is_trip'):
            self._travel_check_trip_entry_sync()
        return super().unlink()

    def _travel_check_trip_entry_sync(self):
        """The calendar entry of a trip is managed from the trip only."""
        if not self.env.context.get('travel_sync'):
            raise UserError(self.env._(
                "The calendar entry of a trip is updated automatically from the trip: "
                "modify the trip instead."))

    def action_open_trip(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'travel.trip',
            'res_id': self.trip_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
