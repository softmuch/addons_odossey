from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# visit states (Omnia-like flow + ophthalmology steps: pre-consultation, dilation, studies)
OPH_STATES = [
    ('booked', "Booked"), ('confirmed', "Confirmed"), ('arrived', "Arrived"),
    ('pre_consultation', "Pre-consultation"), ('dilating', "Dilating"), ('in_studies', "In Studies"),
    ('in_consultation', "In Consultation"), ('done', "Attended"), ('withdrawn', "Left Without Being Seen"),
    ('no_show', "No Show"), ('to_reschedule', "To Reschedule"), ('cancelled', "Cancelled"),
]
WAITING_STATES = ('arrived', 'pre_consultation', 'dilating', 'in_studies')


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    oph_patient_id = fields.Many2one('res.partner', string="Patient", index='btree_not_null',
                                     domain="[('is_oph_patient', '=', True)]")
    oph_record_number = fields.Char(related='oph_patient_id.oph_record_number', string="Clinical Record No.")
    oph_insurance_id = fields.Many2one('oph.insurance', string="Health Insurance",
                                       help="Coverage used for this visit. Taken from the patient; change it for a "
                                            "private visit.")
    oph_member_number = fields.Char(string="Member No.")
    oph_authorization = fields.Char(string="Authorization / Token",
                                    help="Authorization number or token given by the insurer for this visit.")
    oph_appointment_type_id = fields.Many2one('oph.appointment.type', string="Appointment Type")
    oph_room_id = fields.Many2one('oph.room', string="Room")
    oph_reason = fields.Char(string="Reason for Visit",
                             help="What the patient reports when booking. It becomes the reason of the exam. "
                                  "Example: blurred vision in the right eye.")
    oph_state = fields.Selection(OPH_STATES, string="Visit Status", default='booked', tracking=True, index=True,
                                 group_expand='_group_expand_oph_state')
    oph_arrival_time = fields.Datetime(string="Arrival Time", copy=False)
    oph_wait_minutes = fields.Integer(string="Waiting (min)", compute='_compute_oph_wait_minutes',
                                      help="Minutes since the patient arrived, while he is still waiting.")
    oph_alert_html = fields.Html(related='oph_patient_id.oph_alert_html', string="Alerts")
    oph_alert_level = fields.Selection(related='oph_patient_id.oph_alert_level')
    oph_exam_ids = fields.One2many('oph.exam', 'appointment_id', string="Exams")
    oph_reminder_sent = fields.Boolean(string="Reminder Sent", copy=False)
    is_oph_appointment = fields.Boolean(compute='_compute_is_oph_appointment', store=True)

    def _group_expand_oph_state(self, states, domain):
        # waiting room: the columns follow the visit flow (not the alphabetical order) and are always shown
        flow = [key for key, _label in OPH_STATES if key not in ('withdrawn', 'no_show', 'to_reschedule', 'cancelled')]
        return flow + [key for key, _label in OPH_STATES if key not in flow and key in states]

    @api.depends('oph_patient_id', 'oph_appointment_type_id')
    def _compute_is_oph_appointment(self):
        for event in self:
            event.is_oph_appointment = bool(event.oph_patient_id or event.oph_appointment_type_id)

    @api.depends('oph_arrival_time', 'oph_state')
    def _compute_oph_wait_minutes(self):
        now = fields.Datetime.now()
        for event in self:
            if event.oph_arrival_time and event.oph_state in WAITING_STATES:
                event.oph_wait_minutes = int((now - event.oph_arrival_time).total_seconds() // 60)
            else:
                event.oph_wait_minutes = 0

    @api.onchange('oph_appointment_type_id', 'oph_patient_id', 'start')
    def _onchange_oph_appointment(self):
        atype = self.oph_appointment_type_id
        if atype and self.start:
            self.duration = atype.duration / 60.0
            self.stop = self.start + timedelta(minutes=atype.duration)
        if self.oph_patient_id:
            patient = self.oph_patient_id
            self.name = "%s - %s" % (patient.name, atype.name if atype else _("Appointment"))
            self.oph_insurance_id = patient.oph_insurance_id
            self.oph_member_number = patient.oph_member_number
            if patient not in self.partner_ids:
                self.partner_ids = [(4, patient.id)]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('oph_patient_id'):
                patient = self.env['res.partner'].browse(vals['oph_patient_id'])
                atype = self.env['oph.appointment.type'].browse(vals.get('oph_appointment_type_id'))
                if not vals.get('name'):
                    vals['name'] = "%s - %s" % (patient.name, atype.name if atype else _("Appointment"))
                if 'oph_insurance_id' not in vals:
                    vals['oph_insurance_id'] = patient.oph_insurance_id.id
                if 'oph_member_number' not in vals:
                    vals['oph_member_number'] = patient.oph_member_number
                partners = vals.get('partner_ids') or []
                if not any(c[0] in (4, 6) and patient.id in (c[2] if c[0] == 6 else [c[1]]) for c in partners):
                    vals['partner_ids'] = partners + [(4, patient.id)]
                if atype and vals.get('start') and not vals.get('stop'):
                    vals['stop'] = fields.Datetime.to_datetime(vals['start']) + timedelta(minutes=atype.duration)
        return super().create(vals_list)

    def write(self, vals):
        # the waiting room kanban moves the cards between visit states: arrival time starts the waiting counter
        if vals.get('oph_state') in WAITING_STATES and 'oph_arrival_time' not in vals:
            missing = self.filtered(lambda e: not e.oph_arrival_time)
            if missing:
                super(CalendarEvent, missing).write(dict(vals, oph_arrival_time=fields.Datetime.now()))
                rest = self - missing
                return super(CalendarEvent, rest).write(vals) if rest else True
        return super().write(vals)

    # ------------------------------------------------------------------ visit flow
    def _oph_set_state(self, state):
        self.write({'oph_state': state})

    def action_oph_confirm(self):
        self._oph_set_state('confirmed')

    def action_oph_arrived(self):
        for event in self:
            vals = {'oph_state': 'arrived'}
            if not event.oph_arrival_time:
                vals['oph_arrival_time'] = fields.Datetime.now()
            event.write(vals)

    def action_oph_dilating(self):
        self._oph_set_state('dilating')

    def action_oph_in_studies(self):
        self._oph_set_state('in_studies')

    def action_oph_withdrawn(self):
        self._oph_set_state('withdrawn')

    def action_oph_no_show(self):
        self._oph_set_state('no_show')

    def action_oph_to_reschedule(self):
        self._oph_set_state('to_reschedule')

    def action_oph_cancel(self):
        self._oph_set_state('cancelled')

    def _oph_get_or_create_exam(self):
        self.ensure_one()
        if not self.oph_patient_id:
            raise UserError(_("Select the patient of the appointment first."))
        exam = self.oph_exam_ids.filtered(lambda e: e.state != 'cancel')[:1]
        if not exam:
            atype = self.oph_appointment_type_id
            doctor = self.user_id if self.user_id.oph_is_ophthalmologist else self.env['res.users']
            exam = self.env['oph.exam'].create({
                'patient_id': self.oph_patient_id.id,
                'appointment_id': self.id,
                'date': fields.Datetime.now(),
                'reason': self.oph_reason or False,
                'visit_type': atype.visit_type if atype and atype.visit_type != 'surgery' else 'first',
                'doctor_id': doctor.id or False,
                'insurance_id': self.oph_insurance_id.id,
                'authorization': self.oph_authorization,
            })
            if atype.product_id:
                exam.line_ids = [(0, 0, {'product_id': atype.product_id.id, 'quantity': 1})]
            if atype.study_type_id:
                exam.study_ids = [(0, 0, {'study_type_id': atype.study_type_id.id, 'patient_id': exam.patient_id.id})]
        return exam

    def _oph_open_exam(self, exam):
        return {
            'type': 'ir.actions.act_window', 'res_model': 'oph.exam', 'res_id': exam.id,
            'view_mode': 'form', 'name': exam.name,
        }

    def action_oph_start_pre_consultation(self):
        self.ensure_one()
        if not self.oph_arrival_time:
            self.oph_arrival_time = fields.Datetime.now()
        exam = self._oph_get_or_create_exam()
        self.oph_state = 'pre_consultation'
        if exam.state == 'draft':
            exam.state = 'pre_consultation'
        return self._oph_open_exam(exam)

    def action_oph_start_consultation(self):
        self.ensure_one()
        if not self.oph_arrival_time:
            self.oph_arrival_time = fields.Datetime.now()
        exam = self._oph_get_or_create_exam()
        exam.action_start()
        return self._oph_open_exam(exam)

    def action_oph_open_patient(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'res.partner', 'res_id': self.oph_patient_id.id,
            'view_mode': 'form', 'views': [(self.env.ref('odossey_ophthalmology.oph_patient_view_form').id, 'form')],
        }

    def action_oph_whatsapp(self):
        self.ensure_one()
        return self.oph_patient_id._oph_whatsapp_action(self._oph_reminder_message())
