from dateutil.relativedelta import relativedelta
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

SEVERITY_ORDER = {'none': 0, 'info': 1, 'warning': 2, 'danger': 3}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_oph_patient = fields.Boolean(string="Ophthalmology Patient", index=True)
    oph_record_number = fields.Char(string="Clinical Record No.", copy=False, index=True, readonly=True,
                                    help="Number of the clinical record (historia clínica), assigned automatically.")
    oph_document = fields.Char(string="ID Number", help="National identity document (DNI) of the patient.")
    oph_birthdate = fields.Date(string="Date of Birth")
    oph_age = fields.Integer(string="Age", compute='_compute_oph_age')
    oph_gender = fields.Selection([('female', "Female"), ('male', "Male"), ('other', "Other / not stated")],
                                  string="Gender")
    oph_insurance_id = fields.Many2one('oph.insurance', string="Health Insurance", index=True,
                                       help="Obra social or prepaid medicine. Leave empty for private patients.")
    oph_plan_id = fields.Many2one('oph.insurance.plan', string="Plan", domain="[('insurance_id', '=', oph_insurance_id)]")
    oph_member_number = fields.Char(string="Member No.", help="Affiliate number of the patient in the health insurance.")
    oph_occupation = fields.Char(string="Occupation")
    oph_referred_by = fields.Char(string="Referred By", help="Professional or channel that referred the patient.")
    # medical background
    oph_allergy_ids = fields.Many2many('oph.allergy', string="Allergies")
    oph_diabetes = fields.Boolean(string="Diabetes")
    oph_hypertension = fields.Boolean(string="Hypertension")
    oph_anticoagulated = fields.Boolean(string="Anticoagulated / Antiplatelet",
                                        help="Takes anticoagulants or antiplatelet drugs: check before surgery or injections.")
    oph_tamsulosin = fields.Boolean(string="Alpha-blockers (tamsulosin)",
                                    help="Risk of intraoperative floppy iris syndrome in cataract surgery.")
    oph_glaucoma_family = fields.Boolean(string="Family History of Glaucoma")
    oph_contact_lens_user = fields.Boolean(string="Contact Lens User")
    oph_medical_history = fields.Text(string="Medical History",
                                      help="Systemic diseases, previous surgeries and current medication.")
    oph_ocular_history = fields.Text(string="Ocular History",
                                     help="Previous eye diseases, surgeries, trauma, glasses or lenses used.")
    oph_alert_level = fields.Selection([('none', "None"), ('info', "Info"), ('warning', "Warning"), ('danger', "Danger")],
                                       compute='_compute_oph_alerts', string="Alert Level")
    oph_alert_html = fields.Html(compute='_compute_oph_alerts', string="Alerts", sanitize=False)
    # relations
    oph_exam_ids = fields.One2many('oph.exam', 'patient_id', string="Exams")
    oph_study_ids = fields.One2many('oph.study', 'patient_id', string="Studies")
    oph_surgery_ids = fields.One2many('oph.surgery', 'patient_id', string="Surgeries")
    oph_glasses_ids = fields.One2many('oph.glasses.prescription', 'patient_id', string="Glasses Prescriptions")
    oph_prescription_ids = fields.One2many('oph.prescription', 'patient_id', string="Prescriptions")
    oph_consent_ids = fields.One2many('oph.consent', 'patient_id', string="Consents")
    oph_certificate_ids = fields.One2many('oph.certificate', 'patient_id', string="Certificates")
    oph_appointment_ids = fields.One2many('calendar.event', 'oph_patient_id', string="Appointments")
    oph_exam_count = fields.Integer(compute='_compute_oph_counts')
    oph_study_count = fields.Integer(compute='_compute_oph_counts')
    oph_surgery_count = fields.Integer(compute='_compute_oph_counts')
    oph_document_count = fields.Integer(compute='_compute_oph_counts')
    oph_appointment_count = fields.Integer(compute='_compute_oph_counts')
    oph_last_exam_date = fields.Datetime(compute='_compute_oph_last_exam', string="Last Exam")
    oph_next_control_date = fields.Date(string="Next Control", compute='_compute_oph_next_control', store=True,
                                        help="Date of the next control set in the last closed exam.")

    _oph_record_number_uniq = models.Constraint('unique(oph_record_number)', "The clinical record number must be unique.")

    @api.depends('oph_birthdate')
    def _compute_oph_age(self):
        today = fields.Date.context_today(self)
        for partner in self:
            partner.oph_age = relativedelta(today, partner.oph_birthdate).years if partner.oph_birthdate else 0

    @api.depends('oph_allergy_ids', 'oph_diabetes', 'oph_hypertension', 'oph_anticoagulated', 'oph_tamsulosin',
                 'oph_glaucoma_family', 'is_oph_patient')
    def _compute_oph_alerts(self):
        for partner in self:
            pills = []
            for allergy in partner.oph_allergy_ids:
                pills.append((allergy.severity, _("Allergy: %s", allergy.name)))
            if partner.oph_anticoagulated:
                pills.append(('danger', _("Anticoagulated")))
            if partner.oph_tamsulosin:
                pills.append(('warning', _("Alpha-blockers (IFIS risk)")))
            if partner.oph_diabetes:
                pills.append(('warning', _("Diabetes")))
            if partner.oph_hypertension:
                pills.append(('info', _("Hypertension")))
            if partner.oph_glaucoma_family:
                pills.append(('info', _("Family history of glaucoma")))
            level = 'none'
            for severity, __ in pills:
                if SEVERITY_ORDER[severity] > SEVERITY_ORDER[level]:
                    level = severity
            partner.oph_alert_level = level
            css = {'info': 'text-bg-info', 'warning': 'text-bg-warning', 'danger': 'text-bg-danger'}
            partner.oph_alert_html = Markup(' ').join(
                Markup('<span class="badge rounded-pill %s">%s</span>') % (css[severity], escape(label))
                for severity, label in pills) if pills else False

    def _compute_oph_counts(self):
        for partner in self:
            partner.oph_exam_count = len(partner.oph_exam_ids)
            partner.oph_study_count = len(partner.oph_study_ids)
            partner.oph_surgery_count = len(partner.oph_surgery_ids)
            partner.oph_appointment_count = len(partner.oph_appointment_ids)
            partner.oph_document_count = len(partner.oph_glasses_ids) + len(partner.oph_prescription_ids) \
                + len(partner.oph_consent_ids) + len(partner.oph_certificate_ids)

    def _oph_last_done_exam(self):
        self.ensure_one()
        return self.oph_exam_ids.filtered(lambda e: e.state == 'done').sorted('date', reverse=True)[:1]

    @api.depends('oph_exam_ids.state', 'oph_exam_ids.date')
    def _compute_oph_last_exam(self):
        for partner in self:
            partner.oph_last_exam_date = partner._oph_last_done_exam().date

    @api.depends('oph_exam_ids.state', 'oph_exam_ids.next_control_date', 'oph_exam_ids.date')
    def _compute_oph_next_control(self):
        for partner in self:
            partner.oph_next_control_date = partner._oph_last_done_exam().next_control_date

    @api.constrains('oph_birthdate')
    def _check_oph_birthdate(self):
        today = fields.Date.context_today(self)
        for partner in self:
            if partner.oph_birthdate and partner.oph_birthdate > today:
                raise ValidationError(_("The date of birth cannot be in the future."))

    @api.onchange('oph_insurance_id')
    def _onchange_oph_insurance_id(self):
        if self.oph_plan_id and self.oph_plan_id.insurance_id != self.oph_insurance_id:
            self.oph_plan_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_oph_patient') and not vals.get('oph_record_number'):
                vals['oph_record_number'] = self.env['ir.sequence'].sudo().next_by_code('oph.patient')
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_oph_patient'):
            for partner in self.filtered(lambda p: not p.oph_record_number):
                partner.oph_record_number = self.env['ir.sequence'].sudo().next_by_code('oph.patient')
        return res

    @api.depends('name', 'oph_record_number', 'is_oph_patient')
    @api.depends_context('oph_show_record')
    def _compute_display_name(self):
        super()._compute_display_name()
        if self.env.context.get('oph_show_record'):
            for partner in self.filtered(lambda p: p.is_oph_patient and p.oph_record_number):
                partner.display_name = '%s [%s]' % (partner.display_name, partner.oph_record_number)

    def _oph_open(self, xmlid, extra_domain=None, context=None):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        action['domain'] = [('patient_id', '=', self.id)] + (extra_domain or [])
        action['context'] = dict(context or {}, default_patient_id=self.id)
        return action

    def action_oph_view_exams(self):
        return self._oph_open('odossey_ophthalmology.oph_exam_action')

    def action_oph_view_studies(self):
        return self._oph_open('odossey_ophthalmology.oph_study_action')

    def action_oph_view_surgeries(self):
        return self._oph_open('odossey_ophthalmology.oph_surgery_action')

    def action_oph_view_glasses(self):
        return self._oph_open('odossey_ophthalmology.oph_glasses_action')

    def action_oph_view_documents(self):
        return self._oph_open('odossey_ophthalmology.oph_prescription_action')

    def action_oph_view_appointments(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_ophthalmology.oph_appointment_action')
        action['domain'] = [('oph_patient_id', '=', self.id)]
        action['context'] = {'default_oph_patient_id': self.id}
        return action

    def action_oph_new_appointment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'calendar.event', 'view_mode': 'form',
            'views': [(self.env.ref('odossey_ophthalmology.calendar_event_view_form_oph').id, 'form')],
            'name': _("Book Appointment"),
            'context': {'default_oph_patient_id': self.id, 'default_partner_ids': [self.id]},
        }

    def action_oph_new_exam(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'oph.exam', 'view_mode': 'form',
            'name': _("New Exam"), 'context': {'default_patient_id': self.id},
        }

    def action_oph_print_record(self):
        return self.env.ref('odossey_ophthalmology.action_report_clinical_record').report_action(self)

    def _get_report_base_filename(self):
        self.ensure_one()
        return _("Clinical record %s - %s", self.oph_record_number or '', self.name)
