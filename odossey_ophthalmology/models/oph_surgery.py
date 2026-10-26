from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .oph_master import EYE_SELECTION

CHECKLIST_FIELDS = ['check_identity', 'check_site_marked', 'check_fasting', 'check_anticoagulants',
                    'check_allergies', 'check_preop_assessment', 'check_timeout', 'check_iol_verified',
                    'check_count_sign_out']


class OphSurgery(models.Model):
    _name = 'oph.surgery'
    _description = 'Surgery'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'start desc, id desc'

    name = fields.Char(string="Reference", required=True, readonly=True, copy=False, default=lambda self: _("New"))
    patient_id = fields.Many2one('res.partner', string="Patient", required=True, index=True, ondelete='restrict',
                                 domain="[('is_oph_patient', '=', True)]", tracking=True)
    record_number = fields.Char(related='patient_id.oph_record_number', string="Clinical Record No.")
    alert_html = fields.Html(related='patient_id.oph_alert_html', string="Alerts")
    alert_level = fields.Selection(related='patient_id.oph_alert_level')
    exam_id = fields.Many2one('oph.exam', string="Indicated in Exam", index='btree_not_null', ondelete='set null')
    procedure_id = fields.Many2one('oph.procedure', string="Procedure", required=True, tracking=True)
    procedure_kind = fields.Selection(related='procedure_id.kind')
    requires_iol = fields.Boolean(related='procedure_id.requires_iol')
    eye = fields.Selection(EYE_SELECTION, required=True, default='od', tracking=True)
    surgeon_id = fields.Many2one('res.users', string="Surgeon", required=True, tracking=True,
                                 domain="[('oph_is_ophthalmologist', '=', True)]", default=lambda self: self.env.user)
    assistant_id = fields.Many2one('res.users', string="Assistant")
    anesthetist = fields.Char(string="Anesthetist")
    anesthesia = fields.Selection([
        ('topical', "Topical"), ('local', "Local (peribulbar / retrobulbar)"), ('sedation', "Sedation"),
        ('general', "General"),
    ])
    room_id = fields.Many2one('oph.room', string="Operating Room", domain="[('room_type', 'in', ('operating', 'laser'))]",
                              tracking=True)
    start = fields.Datetime(string="Scheduled Start", tracking=True)
    duration = fields.Float(string="Duration (hours)", default=0.5)
    stop = fields.Datetime(string="Scheduled End", compute='_compute_stop', store=True)
    event_id = fields.Many2one('calendar.event', string="Agenda Event", copy=False, readonly=True)
    state = fields.Selection([
        ('planned', "Planned"), ('authorized', "Authorized"), ('confirmed', "Confirmed"),
        ('in_progress', "In Surgery"), ('done', "Done"), ('cancel', "Cancelled"),
    ], default='planned', required=True, tracking=True, copy=False)
    insurance_id = fields.Many2one('oph.insurance', string="Health Insurance")
    authorization = fields.Char(string="Authorization No.", tracking=True)
    authorization_state = fields.Selection([
        ('not_required', "Not required"), ('pending', "Requested"), ('approved', "Approved"), ('rejected', "Rejected"),
    ], default='not_required', tracking=True)
    # pre-operative checklist (WHO surgical safety checklist adapted to eye surgery)
    check_identity = fields.Boolean(string="Identity and procedure confirmed")
    check_site_marked = fields.Boolean(string="Eye marked")
    check_fasting = fields.Boolean(string="Fasting confirmed")
    check_anticoagulants = fields.Boolean(string="Anticoagulants checked")
    check_allergies = fields.Boolean(string="Allergies checked")
    check_preop_assessment = fields.Boolean(string="Pre-operative assessment (lab / ECG / clinical)")
    check_timeout = fields.Boolean(string="Time-out done")
    check_iol_verified = fields.Boolean(string="Lens model and power verified")
    check_count_sign_out = fields.Boolean(string="Sign-out: instruments and materials counted")
    checklist_progress = fields.Integer(compute='_compute_checklist', string="Checklist (%)")
    consent_ok = fields.Boolean(compute='_compute_consent_ok', string="Consent Signed", store=True)
    consent_ids = fields.One2many('oph.consent', 'surgery_id', string="Consents")
    # intraocular lens
    iol_product_id = fields.Many2one('product.product', string="Intraocular Lens", domain="[('oph_kind', '=', 'iol')]")
    iol_lot_id = fields.Many2one('stock.lot', string="Lens Serial / Lot",
                                 domain="[('product_id', '=', iol_product_id)]", copy=False)
    iol_expiration = fields.Datetime(related='iol_lot_id.expiration_date', string="Lens Expiry")
    iol_power = fields.Float(string="Lens Power (D)", digits=(4, 2), aggregator=False)
    iol_formula = fields.Selection([('srk_t', "SRK/T"), ('barrett', "Barrett Universal II"), ('haigis', "Haigis"),
                                    ('hoffer_q', "Hoffer Q"), ('holladay', "Holladay"), ('kane', "Kane")],
                                   string="Formula")
    target_refraction = fields.Float(string="Target Refraction (D)", digits=(4, 2), aggregator=False)
    biometry_id = fields.Many2one('oph.study', string="Biometry", domain="[('patient_id', '=', patient_id), ('kind', '=', 'biometry')]")
    # operative report
    actual_start = fields.Datetime(string="Start Time", copy=False)
    actual_end = fields.Datetime(string="End Time", copy=False)
    protocol = fields.Html(string="Operative Report", help="Surgical technique, findings and incidents.")
    complications = fields.Text()
    postop_instructions = fields.Text(string="Post-op Instructions",
                                      help="Printed for the patient: drops, protection, alarm signs, next control.")
    postop_event_ids = fields.One2many('calendar.event', 'oph_surgery_id', string="Post-op Controls")
    line_ids = fields.One2many('oph.charge', 'surgery_id', string="Charges / Supplies")
    sale_order_ids = fields.One2many('sale.order', 'oph_surgery_id', string="Sale Orders")
    claim_ids = fields.One2many('oph.insurance.claim', 'surgery_id', string="Insurance Services")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    def _compute_access_url(self):
        super()._compute_access_url()
        for surgery in self:
            surgery.access_url = f'/my/ophthalmology/surgeries/{surgery.id}'

    @api.depends('start', 'duration')
    def _compute_stop(self):
        for surgery in self:
            surgery.stop = surgery.start + timedelta(hours=surgery.duration or 0.5) if surgery.start else False

    @api.depends(*CHECKLIST_FIELDS)
    def _compute_checklist(self):
        for surgery in self:
            done = sum(1 for name in CHECKLIST_FIELDS if surgery[name])
            surgery.checklist_progress = int(done * 100 / len(CHECKLIST_FIELDS))

    @api.depends('consent_ids.state')
    def _compute_consent_ok(self):
        for surgery in self:
            surgery.consent_ok = any(c.state == 'signed' for c in surgery.consent_ids)

    @api.constrains('start', 'stop', 'room_id', 'surgeon_id', 'state')
    def _check_overlap(self):
        for surgery in self:
            if not surgery.start or surgery.state == 'cancel':
                continue
            domain = [('id', '!=', surgery.id), ('state', '!=', 'cancel'), ('start', '<', surgery.stop),
                      ('stop', '>', surgery.start)]
            if surgery.room_id and self.search_count(domain + [('room_id', '=', surgery.room_id.id)], limit=1):
                raise ValidationError(_("The operating room %s is already booked at that time.", surgery.room_id.name))
            if self.search_count(domain + [('surgeon_id', '=', surgery.surgeon_id.id)], limit=1):
                raise ValidationError(_("%s already has another surgery at that time.", surgery.surgeon_id.name))

    @api.constrains('iol_lot_id', 'start')
    def _check_iol_expiry(self):
        for surgery in self:
            lot = surgery.iol_lot_id
            if lot and lot.expiration_date and surgery.start and lot.expiration_date < surgery.start:
                raise ValidationError(_("The lens %s expired on %s.", lot.name, fields.Date.to_date(lot.expiration_date)))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('oph.surgery') or _("New")
            patient = self.env['res.partner'].browse(vals.get('patient_id'))
            if patient and 'insurance_id' not in vals:
                vals['insurance_id'] = patient.oph_insurance_id.id
            procedure = self.env['oph.procedure'].browse(vals.get('procedure_id'))
            if procedure:
                vals.setdefault('duration', procedure.duration / 60.0)
                vals.setdefault('anesthesia', procedure.anesthesia)
            insurance = self.env['oph.insurance'].browse(vals.get('insurance_id'))
            if insurance and vals.get('authorization_state', 'not_required') == 'not_required' and not vals.get('authorization'):
                price = insurance._get_price(procedure.product_id, patient.oph_plan_id) if procedure.product_id else False
                if insurance.requires_authorization or (price and price.requires_authorization):
                    vals['authorization_state'] = 'pending'
        surgeries = super().create(vals_list)
        for surgery in surgeries:
            if surgery.procedure_id.product_id and not surgery.line_ids:
                surgery.line_ids = [(0, 0, {'product_id': surgery.procedure_id.product_id.id, 'quantity': 1})]
        surgeries._sync_event()
        return surgeries

    def write(self, vals):
        res = super().write(vals)
        if {'start', 'duration', 'surgeon_id', 'room_id', 'state'} & set(vals):
            self._sync_event()
        return res

    def unlink(self):
        if any(s.state in ('in_progress', 'done') for s in self):
            raise UserError(_("Surgeries already performed are part of the clinical record and cannot be deleted."))
        self.event_id.unlink()
        return super().unlink()

    @api.onchange('procedure_id')
    def _onchange_procedure_id(self):
        if self.procedure_id:
            self.duration = self.procedure_id.duration / 60.0
            self.anesthesia = self.procedure_id.anesthesia

    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        if self.patient_id:
            self.insurance_id = self.patient_id.oph_insurance_id

    @api.onchange('biometry_id', 'eye')
    def _onchange_biometry_id(self):
        study = self.biometry_id
        if study:
            eye = 'os' if self.eye == 'os' else 'od'
            self.iol_power = study['iol_power_%s' % eye]
            self.iol_formula = study.iol_formula
            self.target_refraction = study.target_refraction

    def _eye_label(self):
        self.ensure_one()
        return dict(self._fields['eye']._description_selection(self.env)).get(self.eye)

    def _sync_event(self):
        """Keep a calendar event in the surgeon's agenda for every scheduled surgery."""
        surgery_type = self.env.ref('odossey_ophthalmology.appointment_type_surgery', raise_if_not_found=False)
        for surgery in self:
            if surgery.state == 'cancel' or not surgery.start:
                if surgery.event_id:
                    surgery.event_id.oph_state = 'cancelled'
                continue
            vals = {
                'name': _("Surgery: %(procedure)s %(eye)s - %(patient)s", procedure=surgery.procedure_id.name,
                          eye=surgery._eye_label(), patient=surgery.patient_id.name),
                'start': surgery.start, 'stop': surgery.stop, 'user_id': surgery.surgeon_id.id,
                'oph_patient_id': surgery.patient_id.id, 'oph_room_id': surgery.room_id.id,
                'oph_appointment_type_id': surgery_type.id if surgery_type else False,
                'partner_ids': [(4, surgery.patient_id.id), (4, surgery.surgeon_id.partner_id.id)],
            }
            if surgery.event_id:
                surgery.event_id.write(vals)
            else:
                surgery.event_id = self.env['calendar.event'].create(vals)

    # ------------------------------------------------------------------ flow
    def action_request_authorization(self):
        self.write({'authorization_state': 'pending'})

    def action_authorize(self):
        for surgery in self:
            if surgery.insurance_id and not surgery.authorization:
                raise UserError(_("Write the authorization number given by the insurer."))
            vals = {'authorization_state': 'approved'}
            if surgery.state == 'planned':
                vals['state'] = 'authorized'
            surgery.write(vals)

    def action_confirm(self):
        for surgery in self:
            if not surgery.start or not surgery.room_id:
                raise UserError(_("Set the date and the operating room before confirming the surgery."))
            if surgery.authorization_state in ('pending', 'rejected'):
                raise UserError(_("The surgery is waiting for the insurer's authorization."))
            surgery.state = 'confirmed'
            surgery._sync_event()

    def action_start(self):
        for surgery in self:
            if not surgery.consent_ok:
                raise UserError(_("The informed consent of %s is not signed (Law 26.529).", surgery.patient_id.name))
            if surgery.requires_iol and not (surgery.iol_product_id and surgery.iol_lot_id):
                raise UserError(_("Select the intraocular lens and its serial / lot before starting."))
            missing = [surgery._fields[name].get_description(self.env)['string'] for name in CHECKLIST_FIELDS[:-1]
                       if not surgery[name]]
            if missing:
                raise UserError(_("Complete the safety checklist before starting: %s", ', '.join(missing)))
            surgery.write({'state': 'in_progress', 'actual_start': fields.Datetime.now()})

    def action_done(self):
        for surgery in self:
            if surgery.state != 'in_progress':
                raise UserError(_("Start the surgery before closing it."))
            if not surgery.protocol:
                raise UserError(_("Write the operative report before closing the surgery."))
            if not surgery.check_count_sign_out:
                raise UserError(_("Complete the sign-out of the checklist."))
            surgery.write({'state': 'done', 'actual_end': fields.Datetime.now()})
            if surgery.iol_product_id and surgery.iol_product_id not in surgery.line_ids.product_id:
                surgery.line_ids = [(0, 0, {'product_id': surgery.iol_product_id.id, 'quantity': 1,
                                            'lot_id': surgery.iol_lot_id.id})]
            elif surgery.iol_lot_id:
                surgery.line_ids.filtered(lambda l: l.product_id == surgery.iol_product_id and not l.lot_id).lot_id = surgery.iol_lot_id
            surgery._create_postop_controls()
            surgery.line_ids._oph_bill(surgery.patient_id, surgery.insurance_id, surgery.patient_id.oph_plan_id,
                                       surgery.authorization, origin=surgery)

    def action_cancel(self):
        if any(s.state == 'done' for s in self):
            raise UserError(_("A surgery already performed cannot be cancelled."))
        self.write({'state': 'cancel'})

    def action_reset_planned(self):
        self.filtered(lambda s: s.state == 'cancel').write({'state': 'planned'})

    def _create_postop_controls(self):
        self.ensure_one()
        postop_type = self.env.ref('odossey_ophthalmology.appointment_type_postop', raise_if_not_found=False)
        base = self.actual_end or self.start or fields.Datetime.now()
        for days in self.procedure_id._postop_day_list():
            start = (base + timedelta(days=days)).replace(hour=12, minute=0, second=0, microsecond=0)
            self.env['calendar.event'].create({
                'name': _("Post-op control day %(days)s - %(patient)s", days=days, patient=self.patient_id.name),
                'start': start, 'stop': start + timedelta(minutes=postop_type.duration if postop_type else 15),
                'user_id': self.surgeon_id.id, 'oph_patient_id': self.patient_id.id,
                'oph_appointment_type_id': postop_type.id if postop_type else False,
                'oph_reason': _("Post-operative control (%s)", self.procedure_id.name),
                'oph_surgery_id': self.id,
            })

    def action_prepare_consent(self):
        self.ensure_one()
        template = self.procedure_id.consent_template_id or self.env.ref(
            'odossey_ophthalmology.consent_template_general', raise_if_not_found=False)
        if not template:
            raise UserError(_("Set a consent template on the procedure."))
        consent = self.consent_ids.filtered(lambda c: c.state in ('draft', 'sent'))[:1] or self.env['oph.consent'].create({
            'patient_id': self.patient_id.id, 'template_id': template.id, 'surgery_id': self.id,
            'procedure': '%s - %s' % (self.procedure_id.name, self._eye_label()),
            'doctor_id': self.surgeon_id.id,
        })
        return {'type': 'ir.actions.act_window', 'res_model': 'oph.consent', 'res_id': consent.id, 'view_mode': 'form'}

    def action_view_sale_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_ophthalmology.oph_sale_order_action')
        action['domain'] = [('oph_surgery_id', '=', self.id)]
        return action

    def action_print_protocol(self):
        return self.env.ref('odossey_ophthalmology.action_report_surgery').report_action(self)

    def action_print_implant_card(self):
        return self.env.ref('odossey_ophthalmology.action_report_implant_card').report_action(self)

    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s - %s' % (self.name, self.patient_id.name)


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    oph_surgery_id = fields.Many2one('oph.surgery', string="Surgery", index='btree_not_null', ondelete='set null')
