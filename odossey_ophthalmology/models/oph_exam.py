from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .oph_master import EYE_SELECTION

# Visual acuity: decimal value (key) shown with the usual Argentine notation x/10 and Snellen 20/x
VA_SELECTION = [
    ('2.0', "2.0 (20/10)"), ('1.5', "1.5 (20/13)"), ('1.2', "1.2 (12/10 · 20/16)"), ('1.0', "1.0 (10/10 · 20/20)"),
    ('0.9', "0.9 (9/10 · 20/22)"), ('0.8', "0.8 (8/10 · 20/25)"), ('0.7', "0.7 (7/10 · 20/30)"),
    ('0.6', "0.6 (6/10 · 20/32)"), ('0.5', "0.5 (5/10 · 20/40)"), ('0.4', "0.4 (4/10 · 20/50)"),
    ('0.3', "0.3 (3/10 · 20/63)"), ('0.2', "0.2 (2/10 · 20/100)"), ('0.15', "0.15 (20/130)"),
    ('0.1', "0.1 (1/10 · 20/200)"), ('0.05', "0.05 (20/400)"),
    ('cf', "Counts fingers (CF)"), ('hm', "Hand motion (HM)"), ('lp', "Light perception (LP)"),
    ('nlp', "No light perception (NLP)"),
]
NEAR_VA_SELECTION = [('j1', "J1"), ('j2', "J2"), ('j3', "J3"), ('j4', "J4"), ('j5', "J5"), ('j6', "J6"),
                     ('j7', "J7"), ('j10', "J10"), ('j16', "J16"), ('worse', "Worse than J16")]
IOP_METHOD = [('goldmann', "Goldmann applanation"), ('air', "Non-contact (air puff)"), ('icare', "Rebound (iCare)"),
              ('tonopen', "Tono-Pen"), ('palpation', "Digital palpation")]
LOCS_SELECTION = [('clear', "Clear"), ('1', "Grade 1"), ('2', "Grade 2"), ('3', "Grade 3"), ('4', "Grade 4"),
                  ('5', "Grade 5"), ('pseudophakic', "Pseudophakic (IOL)"), ('aphakic', "Aphakic")]
IOP_HIGH = 21.0

# clinical fields that cannot be modified once the exam is closed (corrections go in addenda)
EYE_FIELDS = [
    'va_sc', 'va_cc', 'va_ph', 'va_near', 'lenso_sph', 'lenso_cyl', 'lenso_axis', 'lenso_add',
    'ar_sph', 'ar_cyl', 'ar_axis', 'rx_sph', 'rx_cyl', 'rx_axis', 'rx_add', 'rx_va', 'k1', 'k2', 'k_axis',
    'iop', 'pachymetry', 'lids', 'conjunctiva', 'cornea', 'anterior_chamber', 'iris', 'lens', 'lens_grade',
    'vitreous', 'disc', 'cup_disc', 'macula', 'vessels', 'periphery', 'gonioscopy',
]


def _eye_fields():
    names = []
    for base in EYE_FIELDS:
        names += ['%s_od' % base, '%s_os' % base]
    return names


CLINICAL_FIELDS = set(_eye_fields()) | {
    'patient_id', 'reason', 'current_illness', 'pupils', 'motility', 'cover_test', 'color_vision', 'stereopsis',
    'iop_method', 'iop_time', 'dilated', 'pd_distance', 'pd_near', 'diagnosis_ids', 'plan', 'patient_instructions',
    'clinical_notes', 'doctor_id', 'technician_id', 'date',
}


class OphExam(models.Model):
    _name = 'oph.exam'
    _description = 'Ophthalmology Exam'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string="Reference", required=True, readonly=True, copy=False, default=lambda self: _("New"))
    patient_id = fields.Many2one('res.partner', string="Patient", required=True, index=True, ondelete='restrict',
                                 domain="[('is_oph_patient', '=', True)]", tracking=True)
    record_number = fields.Char(related='patient_id.oph_record_number', string="Clinical Record No.")
    patient_age = fields.Integer(related='patient_id.oph_age', string="Age")
    alert_html = fields.Html(related='patient_id.oph_alert_html', string="Alerts")
    alert_level = fields.Selection(related='patient_id.oph_alert_level')
    date = fields.Datetime(default=fields.Datetime.now, required=True, tracking=True)
    appointment_id = fields.Many2one('calendar.event', string="Appointment", index='btree_not_null', copy=False)
    visit_type = fields.Selection([
        ('first', "First visit"), ('control', "Control"), ('postop', "Post-operative"), ('emergency', "Emergency"),
        ('study', "Studies"), ('pediatric', "Pediatrics / orthoptics"), ('contact_lens', "Contact lenses"),
    ], default='first', required=True)
    doctor_id = fields.Many2one('res.users', string="Ophthalmologist", tracking=True,
                                domain="[('oph_is_ophthalmologist', '=', True)]", default=lambda self: self._default_doctor())
    technician_id = fields.Many2one('res.users', string="Technician", domain="[('oph_is_technician', '=', True)]",
                                    help="Who performed the pre-consultation measurements.")
    insurance_id = fields.Many2one('oph.insurance', string="Health Insurance",
                                   help="Coverage billed for this visit; empty for a private visit.")
    authorization = fields.Char(string="Authorization / Token")
    state = fields.Selection([
        ('draft', "Draft"), ('pre_consultation', "Pre-consultation"), ('in_progress', "In Consultation"),
        ('done', "Closed"), ('cancel', "Cancelled"),
    ], default='draft', required=True, tracking=True, copy=False)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    # anamnesis
    reason = fields.Char(string="Reason for Visit")
    current_illness = fields.Text(string="Current Illness", help="History of the current complaint.")
    medical_history = fields.Text(related='patient_id.oph_medical_history', readonly=False)
    ocular_history = fields.Text(related='patient_id.oph_ocular_history', readonly=False)

    # visual acuity
    va_sc_od = fields.Selection(VA_SELECTION, string="VA sc OD", help="Distance visual acuity without correction.")
    va_sc_os = fields.Selection(VA_SELECTION, string="VA sc OS")
    va_cc_od = fields.Selection(VA_SELECTION, string="VA cc OD", help="Distance visual acuity with the current correction.")
    va_cc_os = fields.Selection(VA_SELECTION, string="VA cc OS")
    va_ph_od = fields.Selection(VA_SELECTION, string="Pinhole OD")
    va_ph_os = fields.Selection(VA_SELECTION, string="Pinhole OS")
    va_near_od = fields.Selection(NEAR_VA_SELECTION, string="Near VA OD")
    va_near_os = fields.Selection(NEAR_VA_SELECTION, string="Near VA OS")
    # lensometry (current glasses)
    lenso_sph_od = fields.Float(string="Lensometry Sph OD", digits=(4, 2), aggregator=False)
    lenso_cyl_od = fields.Float(string="Lensometry Cyl OD", digits=(4, 2), aggregator=False)
    lenso_axis_od = fields.Integer(string="Lensometry Axis OD", aggregator=False)
    lenso_add_od = fields.Float(string="Lensometry Add OD", digits=(4, 2), aggregator=False)
    lenso_sph_os = fields.Float(string="Lensometry Sph OS", digits=(4, 2), aggregator=False)
    lenso_cyl_os = fields.Float(string="Lensometry Cyl OS", digits=(4, 2), aggregator=False)
    lenso_axis_os = fields.Integer(string="Lensometry Axis OS", aggregator=False)
    lenso_add_os = fields.Float(string="Lensometry Add OS", digits=(4, 2), aggregator=False)
    # auto-refraction
    ar_sph_od = fields.Float(string="Auto-ref Sph OD", digits=(4, 2), aggregator=False)
    ar_cyl_od = fields.Float(string="Auto-ref Cyl OD", digits=(4, 2), aggregator=False)
    ar_axis_od = fields.Integer(string="Auto-ref Axis OD", aggregator=False)
    ar_sph_os = fields.Float(string="Auto-ref Sph OS", digits=(4, 2), aggregator=False)
    ar_cyl_os = fields.Float(string="Auto-ref Cyl OS", digits=(4, 2), aggregator=False)
    ar_axis_os = fields.Integer(string="Auto-ref Axis OS", aggregator=False)
    # subjective refraction
    rx_sph_od = fields.Float(string="Sphere OD", digits=(4, 2), aggregator=False)
    rx_cyl_od = fields.Float(string="Cylinder OD", digits=(4, 2), aggregator=False)
    rx_axis_od = fields.Integer(string="Axis OD", aggregator=False)
    rx_add_od = fields.Float(string="Addition OD", digits=(4, 2), aggregator=False)
    rx_va_od = fields.Selection(VA_SELECTION, string="Best Corrected VA OD")
    rx_sph_os = fields.Float(string="Sphere OS", digits=(4, 2), aggregator=False)
    rx_cyl_os = fields.Float(string="Cylinder OS", digits=(4, 2), aggregator=False)
    rx_axis_os = fields.Integer(string="Axis OS", aggregator=False)
    rx_add_os = fields.Float(string="Addition OS", digits=(4, 2), aggregator=False)
    rx_va_os = fields.Selection(VA_SELECTION, string="Best Corrected VA OS")
    pd_distance = fields.Float(string="PD Distance (mm)", digits=(4, 1), aggregator=False,
                               help="Interpupillary distance for distance vision.")
    pd_near = fields.Float(string="PD Near (mm)", digits=(4, 1), aggregator=False)
    # keratometry
    k1_od = fields.Float(string="K1 OD", digits=(4, 2), aggregator=False, help="Flat keratometry in diopters.")
    k2_od = fields.Float(string="K2 OD", digits=(4, 2), aggregator=False, help="Steep keratometry in diopters.")
    k_axis_od = fields.Integer(string="K Axis OD", aggregator=False)
    k1_os = fields.Float(string="K1 OS", digits=(4, 2), aggregator=False)
    k2_os = fields.Float(string="K2 OS", digits=(4, 2), aggregator=False)
    k_axis_os = fields.Integer(string="K Axis OS", aggregator=False)
    # intraocular pressure
    iop_od = fields.Float(string="IOP OD (mmHg)", digits=(3, 1), aggregator='avg', tracking=True)
    iop_os = fields.Float(string="IOP OS (mmHg)", digits=(3, 1), aggregator='avg', tracking=True)
    iop_method = fields.Selection(IOP_METHOD, string="IOP Method", default='goldmann')
    iop_time = fields.Datetime(string="IOP Time", help="Pressure varies during the day: the time is recorded with it.")
    pachymetry_od = fields.Integer(string="Pachymetry OD (µm)", aggregator=False, help="Central corneal thickness.")
    pachymetry_os = fields.Integer(string="Pachymetry OS (µm)", aggregator=False)
    iop_warning = fields.Char(compute='_compute_iop_warning')
    # motility / pupils / orthoptics
    pupils = fields.Char(help="Example: isocoric, reactive, no RAPD.")
    motility = fields.Char(string="Ocular Motility", help="Example: full, orthophoric.")
    cover_test = fields.Char(string="Cover Test")
    color_vision = fields.Char(string="Color Vision", help="Ishihara result. Example: 15/15.")
    stereopsis = fields.Char(help="Example: Titmus 40 seconds of arc.")
    dilated = fields.Boolean(string="Pupils Dilated", help="Fundus examined with mydriasis.")
    # slit lamp
    lids_od = fields.Char(string="Lids OD")
    lids_os = fields.Char(string="Lids OS")
    conjunctiva_od = fields.Char(string="Conjunctiva OD")
    conjunctiva_os = fields.Char(string="Conjunctiva OS")
    cornea_od = fields.Char(string="Cornea OD")
    cornea_os = fields.Char(string="Cornea OS")
    anterior_chamber_od = fields.Char(string="Anterior Chamber OD", help="Depth (Van Herick) and cells / flare.")
    anterior_chamber_os = fields.Char(string="Anterior Chamber OS")
    iris_od = fields.Char(string="Iris OD")
    iris_os = fields.Char(string="Iris OS")
    lens_od = fields.Char(string="Lens OD")
    lens_os = fields.Char(string="Lens OS")
    lens_grade_od = fields.Selection(LOCS_SELECTION, string="Cataract OD (LOCS)")
    lens_grade_os = fields.Selection(LOCS_SELECTION, string="Cataract OS (LOCS)")
    gonioscopy_od = fields.Char(string="Gonioscopy OD", help="Example: open angle, Shaffer grade 4.")
    gonioscopy_os = fields.Char(string="Gonioscopy OS")
    # fundus
    vitreous_od = fields.Char(string="Vitreous OD")
    vitreous_os = fields.Char(string="Vitreous OS")
    disc_od = fields.Char(string="Optic Disc OD")
    disc_os = fields.Char(string="Optic Disc OS")
    cup_disc_od = fields.Float(string="C/D OD", digits=(2, 2), aggregator=False, help="Vertical cup / disc ratio (0.0-1.0).")
    cup_disc_os = fields.Float(string="C/D OS", digits=(2, 2), aggregator=False)
    macula_od = fields.Char(string="Macula OD")
    macula_os = fields.Char(string="Macula OS")
    vessels_od = fields.Char(string="Vessels OD")
    vessels_os = fields.Char(string="Vessels OS")
    periphery_od = fields.Char(string="Periphery OD")
    periphery_os = fields.Char(string="Periphery OS")

    # assessment and plan
    diagnosis_ids = fields.One2many('oph.exam.diagnosis', 'exam_id', string="Diagnoses")
    main_diagnosis = fields.Char(compute='_compute_main_diagnosis', string="Main Diagnosis")
    plan = fields.Html(help="Treatment plan, studies requested and indications.")
    patient_instructions = fields.Text(string="Instructions for the Patient",
                                       help="Printed on the exam summary given to the patient.")
    clinical_notes = fields.Html(string="Private Notes", groups='odossey_ophthalmology.group_oph_ophthalmologist',
                                 help="Notes visible only to the ophthalmologists; not printed.")
    next_control_date = fields.Date(string="Next Control", tracking=True,
                                    help="Proposed automatically from the chronic diagnoses when the exam is closed.")
    study_ids = fields.One2many('oph.study', 'exam_id', string="Studies")
    glasses_ids = fields.One2many('oph.glasses.prescription', 'exam_id', string="Glasses Prescriptions")
    prescription_ids = fields.One2many('oph.prescription', 'exam_id', string="Prescriptions")
    surgery_ids = fields.One2many('oph.surgery', 'exam_id', string="Surgeries")
    certificate_ids = fields.One2many('oph.certificate', 'exam_id', string="Certificates")
    addendum_ids = fields.One2many('oph.exam.addendum', 'exam_id', string="Addenda")
    line_ids = fields.One2many('oph.charge', 'exam_id', string="Charges")
    sale_order_ids = fields.One2many('sale.order', 'oph_exam_id', string="Sale Orders")
    claim_ids = fields.One2many('oph.insurance.claim', 'exam_id', string="Insurance Services")
    document_count = fields.Integer(compute='_compute_document_count')

    @api.model
    def _default_doctor(self):
        return self.env.user if self.env.user.oph_is_ophthalmologist else False

    @api.depends('iop_od', 'iop_os')
    def _compute_iop_warning(self):
        threshold = float(self.env['ir.config_parameter'].sudo().get_param('odossey_ophthalmology.iop_threshold', IOP_HIGH))
        for exam in self:
            warnings = []
            if exam.iop_od > threshold:
                warnings.append(_("High pressure in the right eye (%s mmHg).", exam.iop_od))
            if exam.iop_os > threshold:
                warnings.append(_("High pressure in the left eye (%s mmHg).", exam.iop_os))
            if exam.iop_od and exam.iop_os and abs(exam.iop_od - exam.iop_os) > 5:
                warnings.append(_("Pressure difference between the eyes above 5 mmHg."))
            exam.iop_warning = ' '.join(warnings) or False

    @api.depends('diagnosis_ids.diagnosis_id', 'diagnosis_ids.eye')
    def _compute_main_diagnosis(self):
        eyes = dict(self.env['oph.exam.diagnosis']._fields['eye']._description_selection(self.env))
        for exam in self:
            first = exam.diagnosis_ids[:1]
            exam.main_diagnosis = '%s (%s)' % (first.diagnosis_id.display_name, eyes.get(first.eye, '')) if first else False

    def _compute_document_count(self):
        for exam in self:
            exam.document_count = len(exam.glasses_ids) + len(exam.prescription_ids) + len(exam.certificate_ids)

    @api.constrains(*['%s_%s' % (base, eye) for base in ('lenso_axis', 'ar_axis', 'rx_axis', 'k_axis') for eye in ('od', 'os')])
    def _check_axes(self):
        for exam in self:
            for base in ('lenso_axis', 'ar_axis', 'rx_axis', 'k_axis'):
                for eye in ('od', 'os'):
                    if not 0 <= exam['%s_%s' % (base, eye)] <= 180:
                        raise ValidationError(_("Axes must be between 0 and 180 degrees."))

    @api.constrains('iop_od', 'iop_os', 'cup_disc_od', 'cup_disc_os')
    def _check_ranges(self):
        for exam in self:
            if not (0 <= exam.iop_od <= 80 and 0 <= exam.iop_os <= 80):
                raise ValidationError(_("Intraocular pressure must be between 0 and 80 mmHg."))
            if not (0 <= exam.cup_disc_od <= 1 and 0 <= exam.cup_disc_os <= 1):
                raise ValidationError(_("The cup / disc ratio must be between 0 and 1."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('oph.exam') or _("New")
            if vals.get('patient_id') and 'insurance_id' not in vals:
                vals['insurance_id'] = self.env['res.partner'].browse(vals['patient_id']).oph_insurance_id.id
        return super().create(vals_list)

    def write(self, vals):
        if CLINICAL_FIELDS & set(vals) and not self.env.context.get('oph_allow_closed_edit') \
                and any(exam.state == 'done' for exam in self):
            raise UserError(_("A closed exam cannot be modified: add an addendum to correct or complete it."))
        return super().write(vals)

    def unlink(self):
        if any(exam.state == 'done' for exam in self):
            raise UserError(_("Closed exams are part of the clinical record and cannot be deleted."))
        return super().unlink()

    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        if self.patient_id:
            self.insurance_id = self.patient_id.oph_insurance_id

    def web_read(self, specification):
        # Law 25.326: every opening of a clinical record is logged (who and when)
        result = super().web_read(specification)
        if len(self) == 1 and not self.env.su:
            self.env['oph.access.log'].sudo().create({
                'user_id': self.env.uid, 'res_model': self._name, 'res_id': self.id,
                'patient_id': self.patient_id.id,
            })
        return result

    # ------------------------------------------------------------------ flow
    def action_pre_consultation(self):
        self.filtered(lambda e: e.state == 'draft').write({'state': 'pre_consultation'})
        for exam in self:
            if not exam.technician_id and self.env.user.oph_is_technician:
                exam.technician_id = self.env.user
            if exam.appointment_id:
                exam.appointment_id.oph_state = 'pre_consultation'

    def action_start(self):
        for exam in self:
            if exam.state in ('done', 'cancel'):
                continue
            vals = {'state': 'in_progress'}
            if not exam.doctor_id and self.env.user.oph_is_ophthalmologist:
                vals['doctor_id'] = self.env.user.id
            exam.write(vals)
            if exam.appointment_id:
                exam.appointment_id.oph_state = 'in_consultation'

    def _suggest_next_control(self):
        self.ensure_one()
        months = [m for m in self.diagnosis_ids.diagnosis_id.mapped('control_months') if m]
        if months:
            return fields.Date.context_today(self) + relativedelta(months=min(months))
        return False

    def action_done(self):
        for exam in self:
            if exam.state in ('done', 'cancel'):
                continue
            if not exam.doctor_id:
                raise UserError(_("Set the ophthalmologist who attended the patient before closing the exam."))
            if not exam.diagnosis_ids:
                raise UserError(_("Record at least one diagnosis before closing the exam."))
            vals = {'state': 'done'}
            if not exam.next_control_date:
                vals['next_control_date'] = exam._suggest_next_control()
            exam.with_context(oph_allow_closed_edit=True).write(vals)
            if exam.appointment_id:
                exam.appointment_id.oph_state = 'done'
            if exam.next_control_date:
                exam.activity_schedule(
                    'mail.mail_activity_data_todo', date_deadline=exam.next_control_date,
                    summary=_("Control of %s", exam.patient_id.name), user_id=exam.doctor_id.id)
            if exam.line_ids and self.env['ir.config_parameter'].sudo().get_param('odossey_ophthalmology.auto_billing', 'True') == 'True':
                exam.action_create_billing()

    def action_cancel(self):
        if any(exam.state == 'done' for exam in self):
            raise UserError(_("A closed exam cannot be cancelled."))
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        self.filtered(lambda e: e.state == 'cancel').write({'state': 'draft'})

    def action_copy_previous(self):
        """Pull forward the previous closed exam: refraction becomes the lensometry, background notes are copied."""
        for exam in self:
            previous = self.search([('patient_id', '=', exam.patient_id.id), ('state', '=', 'done'),
                                    ('id', '!=', exam.id)], order='date desc', limit=1)
            if not previous:
                raise UserError(_("%s has no previous closed exam.", exam.patient_id.name))
            vals = {}
            for eye in ('od', 'os'):
                for src, dst in (('rx_sph', 'lenso_sph'), ('rx_cyl', 'lenso_cyl'), ('rx_axis', 'lenso_axis'),
                                 ('rx_add', 'lenso_add')):
                    vals['%s_%s' % (dst, eye)] = previous['%s_%s' % (src, eye)]
                for name in ('lids', 'conjunctiva', 'cornea', 'anterior_chamber', 'iris', 'lens', 'lens_grade',
                             'gonioscopy', 'vitreous', 'disc', 'cup_disc', 'macula', 'vessels', 'periphery'):
                    if not exam['%s_%s' % (name, eye)]:
                        vals['%s_%s' % (name, eye)] = previous['%s_%s' % (name, eye)]
            exam.write(vals)
            if not exam.diagnosis_ids:
                exam.diagnosis_ids = [(0, 0, {'diagnosis_id': d.diagnosis_id.id, 'eye': d.eye, 'note': d.note})
                                      for d in previous.diagnosis_ids]
            exam.message_post(body=_("Data copied from the previous exam %s.", previous.name))

    def action_create_glasses(self):
        self.ensure_one()
        values = {'patient_id': self.patient_id.id, 'exam_id': self.id, 'doctor_id': (self.doctor_id or self.env.user).id,
                  'pd_distance': self.pd_distance, 'pd_near': self.pd_near}
        for eye in ('od', 'os'):
            for name in ('sph', 'cyl', 'axis', 'add'):
                values['%s_%s' % (name, eye)] = self['rx_%s_%s' % (name, eye)]
        if self.rx_add_od or self.rx_add_os:
            values['lens_use'] = 'progressive'
        glasses = self.env['oph.glasses.prescription'].create(values)
        return {'type': 'ir.actions.act_window', 'res_model': 'oph.glasses.prescription', 'res_id': glasses.id,
                'view_mode': 'form'}

    def action_new_prescription(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'oph.prescription', 'view_mode': 'form',
                'context': {'default_patient_id': self.patient_id.id, 'default_exam_id': self.id,
                            'default_doctor_id': (self.doctor_id or self.env.user).id,
                            'default_diagnosis_id': self.diagnosis_ids[:1].diagnosis_id.id}}

    def action_new_surgery(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'oph.surgery', 'view_mode': 'form',
                'context': {'default_patient_id': self.patient_id.id, 'default_exam_id': self.id,
                            'default_surgeon_id': (self.doctor_id or self.env.user).id}}

    def action_new_certificate(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'oph.certificate', 'view_mode': 'form',
                'context': {'default_patient_id': self.patient_id.id, 'default_exam_id': self.id,
                            'default_doctor_id': (self.doctor_id or self.env.user).id}}

    def action_view_documents(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_ophthalmology.oph_glasses_action')
        action['domain'] = [('exam_id', '=', self.id)]
        return action

    def action_create_billing(self):
        for exam in self:
            exam.line_ids._oph_bill(exam.patient_id, exam.insurance_id, exam.patient_id.oph_plan_id,
                                    exam.authorization, origin=exam)

    def action_view_sale_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_ophthalmology.oph_sale_order_action')
        action['domain'] = [('oph_exam_id', '=', self.id)]
        return action

    def action_open_iop_chart(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_ophthalmology.oph_exam_evolution_action')
        action['domain'] = [('patient_id', '=', self.patient_id.id), ('state', '=', 'done')]
        action['display_name'] = _("Evolution of %s", self.patient_id.name)
        return action

    def action_print(self):
        return self.env.ref('odossey_ophthalmology.action_report_exam').report_action(self)

    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s - %s' % (self.name, self.patient_id.name)


class OphExamDiagnosis(models.Model):
    _name = 'oph.exam.diagnosis'
    _description = 'Exam Diagnosis'
    _order = 'sequence, id'

    exam_id = fields.Many2one('oph.exam', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    diagnosis_id = fields.Many2one('oph.diagnosis', string="Diagnosis", required=True)
    eye = fields.Selection(EYE_SELECTION, default='ou', required=True)
    note = fields.Char()
    patient_id = fields.Many2one(related='exam_id.patient_id', store=True)
    date = fields.Datetime(related='exam_id.date', store=True)


class OphExamAddendum(models.Model):
    _name = 'oph.exam.addendum'
    _description = 'Exam Addendum'
    _order = 'create_date, id'

    exam_id = fields.Many2one('oph.exam', required=True, ondelete='cascade', index=True)
    note = fields.Text(required=True)
    author_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)
    create_date = fields.Datetime(string="Date", readonly=True)

    def write(self, vals):
        raise UserError(_("Addenda cannot be modified: add a new one."))

    def unlink(self):
        raise UserError(_("Addenda are part of the clinical record and cannot be deleted."))


class OphAccessLog(models.Model):
    _name = 'oph.access.log'
    _description = 'Clinical Record Access Log'
    _order = 'create_date desc, id desc'
    _log_access = True

    user_id = fields.Many2one('res.users', string="User", readonly=True, index=True)
    patient_id = fields.Many2one('res.partner', string="Patient", readonly=True, index=True)
    res_model = fields.Char(string="Document Type", readonly=True)
    res_id = fields.Integer(string="Document ID", readonly=True)
    create_date = fields.Datetime(string="Date", readonly=True)
