from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class VetAppointmentType(models.Model):
    _name = 'vet.appointment.type'
    _description = 'Appointment Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    duration = fields.Integer(string="Duration (min)", default=30, required=True)
    consultation_type = fields.Selection([
        ('consultation', "Consultation"), ('control', "Follow-up"), ('emergency', "Emergency"),
        ('vaccination', "Vaccination / Preventive"), ('surgery', "Surgery"), ('home_visit', "Home visit"),
        ('telemedicine', "Telemedicine"), ('grooming', "Grooming"),
    ], default='consultation', required=True)
    product_id = fields.Many2one('product.product', string="Service", help="Service charged for this kind of appointment.")
    template_id = fields.Many2one('vet.consultation.template', string="Consultation Template")
    color = fields.Integer()
    active = fields.Boolean(default=True)


class VetRoom(models.Model):
    _name = 'vet.room'
    _description = 'Consulting Room / Resource'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    room_type = fields.Selection([
        ('consulting', "Consulting room"), ('surgery', "Operating room"), ('grooming', "Grooming"),
        ('imaging', "Imaging"), ('other', "Other"),
    ], default='consulting')
    active = fields.Boolean(default=True)


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    vet_pet_id = fields.Many2one('vet.pet', string="Patient", index='btree_not_null')
    vet_owner_id = fields.Many2one(related='vet_pet_id.owner_id', string="Owner")
    vet_appointment_type_id = fields.Many2one('vet.appointment.type', string="Appointment Type")
    vet_room_id = fields.Many2one('vet.room', string="Room")
    vet_reason = fields.Char(string="Reason for Visit",
                             help="What the owner reports when booking. It becomes the reason of the consultation. "
                                  "Example: vomiting since yesterday.")
    vet_state = fields.Selection([
        ('booked', "Booked"), ('confirmed', "Confirmed"), ('arrived', "Arrived"),
        ('in_consultation', "In Consultation"), ('done', "Done"), ('no_show', "No Show"), ('cancelled', "Cancelled"),
    ], string="Visit Status", default='booked', tracking=True)
    vet_consultation_ids = fields.One2many('vet.consultation', 'appointment_id', string="Consultations")
    is_vet_appointment = fields.Boolean(compute='_compute_is_vet_appointment', store=True)
    vet_veterinarian_id = fields.Many2one(
        'res.users', string="Veterinarian", compute='_compute_vet_veterinarian_id', inverse='_inverse_vet_veterinarian_id',
        store=True, index='btree_not_null',
        domain="[('vet_is_veterinarian', '=', True), ('share', '=', False)]",
        help="Professional who attends the appointment. Only users marked as veterinarians are listed. Example: Dra. Ana Torres.")

    # Phone booking: the appointment is booked with the minimum data; the patient record is completed on arrival
    vet_contact_name = fields.Char(string="Contact Name",
                                   help="Who booked the appointment when the owner is not registered yet. Example: Marta (phone call).")
    vet_contact_phone = fields.Char(string="Contact Phone",
                                    help="Phone to confirm or move the appointment. Example: 351 555-1234.")
    vet_contact_pet_name = fields.Char(string="Pet Name",
                                       help="Name of the animal, while it has no clinical record. Example: Toby.")
    vet_contact_species_id = fields.Many2one('vet.species', string="Species ",
                                             help="Species told on the phone, used when the patient is registered.")
    vet_is_provisional = fields.Boolean(compute='_compute_vet_card', string="Patient to Register",
                                        help="Booked without a clinical record: register owner and patient when they arrive.")

    vet_card_color = fields.Integer(compute='_compute_vet_agenda_options',
                                    help="Color of the appointment in the agenda (Settings › Veterinary › Colors).")
    vet_use_rooms = fields.Boolean(compute='_compute_vet_agenda_options')
    vet_require_veterinarian = fields.Boolean(compute='_compute_vet_agenda_options')

    # Information shown inside the agenda cell (the reception reads it without opening the appointment)
    vet_card_pet = fields.Char(compute='_compute_vet_card')
    vet_card_species = fields.Char(compute='_compute_vet_card')
    vet_card_species_icon = fields.Char(compute='_compute_vet_card')
    vet_card_owner = fields.Char(compute='_compute_vet_card')
    vet_card_phone = fields.Char(compute='_compute_vet_card')
    vet_card_alert = fields.Char(compute='_compute_vet_card')
    vet_card_danger = fields.Boolean(compute='_compute_vet_card')
    vet_card_status = fields.Char(compute='_compute_vet_card')
    vet_card_status_label = fields.Char(compute='_compute_vet_card')

    @api.depends('vet_pet_id', 'vet_contact_name', 'vet_contact_phone', 'vet_contact_pet_name', 'vet_contact_species_id',
                 'vet_state', 'vet_pet_id.species_id.icon', 'vet_contact_species_id.icon')
    @api.depends_context('lang')
    def _compute_vet_card(self):
        for event in self:
            pet = event.vet_pet_id
            event.vet_is_provisional = not pet and bool(event.vet_contact_name or event.vet_contact_pet_name
                                                       or event.vet_contact_phone)
            event.vet_card_pet = pet.name or event.vet_contact_pet_name or False
            species = pet.species_id or event.vet_contact_species_id
            event.vet_card_species = species.name or False
            event.vet_card_species_icon = species.icon_url or False
            event.vet_card_owner = pet.owner_id.name or event.vet_contact_name or False
            event.vet_card_phone = pet.owner_id.phone or event.vet_contact_phone or False
            event.vet_card_alert = pet.alert_summary or False
            event.vet_card_danger = pet.has_danger_alert
            event.vet_card_status, event.vet_card_status_label = event._vet_card_status()

    @api.depends('vet_veterinarian_id.vet_color', 'vet_appointment_type_id.color', 'vet_room_id')
    @api.depends_context('uid')
    def _compute_vet_agenda_options(self):
        options = self._vet_agenda_options()
        color_by = self._vet_agenda_param('agenda_color_by', 'vet_appointment_type_id')
        for event in self:
            event.vet_use_rooms = options['use_rooms']
            event.vet_require_veterinarian = options['require_veterinarian']
            record = event[color_by] if color_by in ('vet_veterinarian_id', 'vet_appointment_type_id', 'vet_room_id') else False
            # the color chosen for the veterinarian / type; otherwise a fixed color per record (11 colors)
            color = (record.vet_color if color_by == 'vet_veterinarian_id' else record.color if color_by == 'vet_appointment_type_id' else 0) if record else 0
            event.vet_card_color = color or (record.id % 11 + 1 if record else 0)

    @api.model
    def _vet_agenda_param(self, key, default):
        value = self.env['ir.config_parameter'].sudo().get_param('odossey_veterinary.%s' % key)
        if value is None or value is False:
            return default
        if isinstance(default, bool):
            return value not in ('False', 'false', '0', '')
        return value

    @api.model
    def _vet_agenda_options(self):
        return {
            'use_rooms': self.env.user.has_group('odossey_veterinary.group_vet_use_rooms'),
            'require_veterinarian': self._vet_agenda_param('agenda_require_veterinarian', False),
        }

    @api.model
    def _vet_default_appointment_type(self):
        type_id = self._vet_agenda_param('default_appointment_type_id', None)
        atype = self.env['vet.appointment.type'].browse(int(type_id)).exists() if type_id and str(type_id).isdigit() else False
        return atype or self.env.ref('odossey_veterinary.appointment_type_consultation', raise_if_not_found=False)

    def _vet_card_status(self):
        """Status shown in the agenda cell: (key, label)."""
        self.ensure_one()
        labels = dict(self._fields['vet_state']._description_selection(self.env))
        return self.vet_state or False, labels.get(self.vet_state, False)

    @api.depends('user_id')
    def _compute_vet_veterinarian_id(self):
        for event in self:
            event.vet_veterinarian_id = event.user_id if event.user_id.vet_is_veterinarian else False

    def _inverse_vet_veterinarian_id(self):
        for event in self:
            if event.vet_veterinarian_id:
                event.user_id = event.vet_veterinarian_id

    @api.depends('vet_pet_id', 'vet_appointment_type_id')
    def _compute_is_vet_appointment(self):
        for event in self:
            event.is_vet_appointment = bool(event.vet_pet_id or event.vet_appointment_type_id)

    @api.model
    def _vet_title(self, pet_name, contact_name, atype):
        who = pet_name or contact_name
        kind = atype.name if atype else _("Appointment")
        return "%s - %s" % (who, kind) if who else kind

    @api.onchange('vet_appointment_type_id', 'vet_pet_id', 'start')
    def _onchange_vet_appointment(self):
        atype = self.vet_appointment_type_id
        if atype and self.start:
            self.duration = atype.duration / 60.0
            self.stop = self.start + timedelta(minutes=atype.duration)
        if self.vet_pet_id:
            owner = self.vet_pet_id.owner_id
            self.name = self._vet_title(self.vet_pet_id.name, False, atype)
            if owner and owner not in self.partner_ids:
                self.partner_ids = [(4, owner.id)]
        elif self.vet_contact_pet_name or self.vet_contact_name:
            self.name = self._vet_title(self.vet_contact_pet_name, self.vet_contact_name, atype)

    @api.onchange('vet_contact_pet_name', 'vet_contact_name')
    def _onchange_vet_contact(self):
        if not self.vet_pet_id and (self.vet_contact_pet_name or self.vet_contact_name):
            self.name = self._vet_title(self.vet_contact_pet_name, self.vet_contact_name, self.vet_appointment_type_id)

    # ------------------------------------------------------------------ agenda settings
    @api.model
    def _vet_agenda_slot_minutes(self):
        value = self.env['ir.config_parameter'].sudo().get_param('odossey_veterinary.agenda_slot_minutes', 15)
        try:
            return max(5, min(120, int(value)))
        except (TypeError, ValueError):
            return 15

    @api.model
    def _vet_opening_calendar(self):
        return self.env.company.resource_calendar_id

    @api.model
    def _vet_clinic_tz(self):
        calendar = self._vet_opening_calendar()
        return pytz.timezone(calendar.tz or self.env.company.partner_id.tz or self.env.user.tz or 'UTC')

    @api.model
    def _vet_opening_hours(self):
        """Opening periods of the clinic per weekday (0 = Monday), in the clinic time zone, as (from, to) hours."""
        calendar = self._vet_opening_calendar()
        hours = {}
        for att in calendar.attendance_ids.filtered(lambda a: not a.display_type and a.day_period != 'lunch'):
            hours.setdefault(int(att.dayofweek), []).append((att.hour_from, att.hour_to))
        return {day: sorted(periods) for day, periods in hours.items()}

    @api.model
    def vet_get_agenda_settings(self):
        """Opening hours (FullCalendar businessHours, in the time zone of the user, who sees the agenda in it),
        slot length and row height of the agenda."""
        ICP = self.env['ir.config_parameter'].sudo()
        clinic_tz = self._vet_clinic_tz()
        user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or clinic_tz.zone)
        today = fields.Date.context_today(self)
        business_hours = []

        def to_user(day, value):
            local = clinic_tz.localize(datetime.combine(today, time.min) + timedelta(hours=value))
            moved = local.astimezone(user_tz)
            shift = (moved.date() - today).days
            return (day + shift) % 7, moved.hour * 60 + moved.minute

        for day, periods in self._vet_opening_hours().items():
            for hour_from, hour_to in periods:
                day_from, minute_from = to_user(day, hour_from)
                day_to, minute_to = to_user(day, hour_to)
                if day_to != day_from:  # the period crosses midnight in the user's time zone: keep the day part
                    minute_to = 24 * 60
                business_hours.append({
                    'daysOfWeek': [(day_from + 1) % 7],  # FullCalendar: 0 = Sunday
                    'startTime': '%02d:%02d' % divmod(minute_from, 60),
                    'endTime': '%02d:%02d' % divmod(minute_to, 60),
                })
        color_by = self._vet_agenda_param('agenda_color_by', 'vet_appointment_type_id')
        return {
            'business_hours': business_hours,
            'slot_minutes': self._vet_agenda_slot_minutes(),
            'row_height': ICP.get_param('odossey_veterinary.agenda_row_height', 'comfortable') or 'comfortable',
            'default_scale': self._vet_agenda_param('agenda_default_scale', 'day'),
            'use_rooms': self._vet_agenda_options()['use_rooms'],
            'hide_closed_days': self._vet_agenda_param('agenda_hide_closed_days', True),
            'color_by': color_by if color_by in ('vet_veterinarian_id', 'vet_appointment_type_id', 'vet_room_id') else False,
            'card': {key: self._vet_agenda_param('agenda_card_%s' % key, True)
                     for key in ('species', 'owner', 'phone', 'veterinarian', 'reason', 'alerts', 'status')},
        }

    @api.model
    def _vet_next_slot(self, now=None):
        """Next free time of the grid: today from now on, aligned to the slots counted from the opening time
        (8:40 → 8:40, 9:00, 9:20...), skipping closed hours; tomorrow's opening when the day is over."""
        slot = self._vet_agenda_slot_minutes()
        clinic_tz = self._vet_clinic_tz()
        now = now or fields.Datetime.now()
        local_now = pytz.utc.localize(now).astimezone(clinic_tz).replace(tzinfo=None)
        hours = self._vet_opening_hours()
        if not hours:
            minutes = -(-(local_now.hour * 60 + local_now.minute) // slot) * slot
            local = datetime.combine(local_now.date(), time.min) + timedelta(minutes=minutes)
        else:
            local = None
            for offset in range(8):
                day = local_now.date() + timedelta(days=offset)
                for hour_from, hour_to in hours.get(day.weekday(), []):
                    start = datetime.combine(day, time.min) + timedelta(minutes=round(hour_from * 60))
                    end = datetime.combine(day, time.min) + timedelta(minutes=round(hour_to * 60))
                    candidate = start
                    if candidate < local_now:
                        steps = -(-(local_now - start) // timedelta(minutes=slot))
                        candidate = start + timedelta(minutes=slot * steps)
                    if candidate + timedelta(minutes=slot) <= end:
                        local = candidate
                        break
                if local:
                    break
            local = local or local_now.replace(second=0, microsecond=0)
        return clinic_tz.localize(local).astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        if ctx.get('vet_agenda') and 'vet_appointment_type_id' in fields_list and not ctx.get('default_vet_appointment_type_id'):
            atype = self._vet_default_appointment_type()
            if atype:
                res['vet_appointment_type_id'] = atype.id
                if res.get('start') and 'stop' in fields_list and ctx.get('default_start') and not ctx.get('default_stop'):
                    res['stop'] = fields.Datetime.to_datetime(res['start']) + timedelta(minutes=atype.duration)
        if ctx.get('vet_agenda') and 'start' in fields_list and not ctx.get('default_start'):
            start = self._vet_next_slot()
            res['start'] = start
            atype = self.env['vet.appointment.type'].browse(res.get('vet_appointment_type_id') or ctx.get('default_vet_appointment_type_id'))
            minutes = atype.exists().duration or self._vet_agenda_slot_minutes()
            if 'stop' in fields_list:
                res['stop'] = start + timedelta(minutes=minutes)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('vet_pet_id') and not vals.get('name') and (vals.get('vet_contact_pet_name') or vals.get('vet_contact_name')):
                atype = self.env['vet.appointment.type'].browse(vals.get('vet_appointment_type_id'))
                vals['name'] = self._vet_title(vals.get('vet_contact_pet_name'), vals.get('vet_contact_name'), atype)
            if not vals.get('name') and vals.get('vet_appointment_type_id') and not vals.get('vet_pet_id'):
                vals['name'] = self.env['vet.appointment.type'].browse(vals['vet_appointment_type_id']).name
            if vals.get('vet_appointment_type_id') and vals.get('start') and not vals.get('stop') and not vals.get('vet_pet_id'):
                atype = self.env['vet.appointment.type'].browse(vals['vet_appointment_type_id'])
                vals['stop'] = fields.Datetime.to_datetime(vals['start']) + timedelta(minutes=atype.duration)
            if vals.get('vet_pet_id'):
                pet = self.env['vet.pet'].browse(vals['vet_pet_id'])
                atype = self.env['vet.appointment.type'].browse(vals.get('vet_appointment_type_id'))
                if not vals.get('name'):
                    vals['name'] = "%s - %s" % (pet.name, atype.name if atype else _("Appointment"))
                partners = vals.get('partner_ids') or []
                if pet.owner_id and not any(c[0] in (4, 6) and pet.owner_id.id in (c[2] if c[0] == 6 else [c[1]]) for c in partners):
                    vals['partner_ids'] = partners + [(4, pet.owner_id.id)]
                if atype and vals.get('start') and not vals.get('stop'):
                    vals['stop'] = fields.Datetime.to_datetime(vals['start']) + timedelta(minutes=atype.duration)
        return super().create(vals_list)

    def action_vet_arrived(self):
        self.write({'vet_state': 'arrived'})

    def action_vet_confirm(self):
        self.write({'vet_state': 'confirmed'})

    def action_vet_no_show(self):
        self.write({'vet_state': 'no_show'})

    def action_vet_register_patient(self):
        """Phone booking: register the owner and the patient with the data taken on the phone."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vet.appointment.register', 'view_mode': 'form',
            'target': 'new', 'name': _("Register Patient"),
            'context': {'default_appointment_id': self.id,
                        'vet_start_consultation': self.env.context.get('vet_start_consultation')},
        }

    def action_vet_start_consultation(self):
        self.ensure_one()
        if not self.vet_pet_id:
            if self.vet_is_provisional:
                return self.with_context(vet_start_consultation=True).action_vet_register_patient()
            raise UserError(_("Select the patient of the appointment first."))
        consultation = self.vet_consultation_ids.filtered(lambda c: c.state != 'cancel')[:1]
        if not consultation:
            atype = self.vet_appointment_type_id
            vet = self.user_id if self.user_id.vet_is_veterinarian else self.env.user
            vals = {
                'pet_id': self.vet_pet_id.id,
                'appointment_id': self.id,
                'date': self.start,
                'reason': self.vet_reason or False,
                'consultation_type': atype.consultation_type if atype and atype.consultation_type != 'grooming' else 'consultation',
                'weight': self.vet_pet_id.weight,
            }
            if vet.vet_is_veterinarian:
                vals['vet_id'] = vet.id
            consultation = self.env['vet.consultation'].create(vals)
            if atype.template_id:
                consultation.template_id = atype.template_id
                consultation._onchange_template_id()
            if atype.product_id and atype.product_id not in consultation.line_ids.product_id:
                consultation.line_ids = [(0, 0, {'product_id': atype.product_id.id, 'quantity': 1})]
        consultation.action_start()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vet.consultation', 'res_id': consultation.id,
            'view_mode': 'form', 'name': consultation.name,
        }


class VetPet(models.Model):
    _inherit = 'vet.pet'

    appointment_ids = fields.One2many('calendar.event', 'vet_pet_id', string="Appointments")
    appointment_count = fields.Integer(compute='_compute_appointment_count')

    def _compute_appointment_count(self):
        for pet in self:
            pet.appointment_count = len(pet.appointment_ids)

    def action_view_appointments(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_veterinary.vet_appointment_action')
        action['domain'] = [('vet_pet_id', '=', self.id)]
        action['context'] = {'default_vet_pet_id': self.id}
        return action

    def action_new_appointment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'calendar.event', 'view_mode': 'form',
            'views': [(self.env.ref('odossey_veterinary.calendar_event_view_form_vet').id, 'form')],
            'name': _("Book Appointment"),
            'context': {'default_vet_pet_id': self.id, 'default_partner_ids': [self.owner_id.id]},
        }
