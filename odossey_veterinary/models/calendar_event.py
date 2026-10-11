from datetime import timedelta

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

    @api.depends('vet_pet_id', 'vet_appointment_type_id')
    def _compute_is_vet_appointment(self):
        for event in self:
            event.is_vet_appointment = bool(event.vet_pet_id or event.vet_appointment_type_id)

    @api.onchange('vet_appointment_type_id', 'vet_pet_id', 'start')
    def _onchange_vet_appointment(self):
        atype = self.vet_appointment_type_id
        if atype and self.start:
            self.duration = atype.duration / 60.0
            self.stop = self.start + timedelta(minutes=atype.duration)
        if self.vet_pet_id:
            owner = self.vet_pet_id.owner_id
            self.name = "%s - %s" % (self.vet_pet_id.name, atype.name if atype else _("Appointment"))
            if owner and owner not in self.partner_ids:
                self.partner_ids = [(4, owner.id)]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
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

    def action_vet_start_consultation(self):
        self.ensure_one()
        if not self.vet_pet_id:
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
