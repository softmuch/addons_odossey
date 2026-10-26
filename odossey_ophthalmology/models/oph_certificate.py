from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

VA_LABELS = {'cf': "CF", 'hm': "HM", 'lp': "LP", 'nlp': "NLP"}


class OphCertificate(models.Model):
    _name = 'oph.certificate'
    _description = 'Medical Certificate'
    _inherit = ['portal.mixin', 'mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string="Reference", required=True, readonly=True, copy=False, default=lambda self: _("New"))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    patient_id = fields.Many2one('res.partner', string="Patient", required=True, index=True, ondelete='restrict',
                                 domain="[('is_oph_patient', '=', True)]")
    exam_id = fields.Many2one('oph.exam', string="Exam", index='btree_not_null', ondelete='set null')
    doctor_id = fields.Many2one('res.users', string="Ophthalmologist", required=True,
                                domain="[('oph_is_ophthalmologist', '=', True)]", default=lambda self: self.env.user)
    date = fields.Date(default=fields.Date.context_today, required=True)
    certificate_type = fields.Selection([
        ('visual_fitness', "Visual fitness (driving licence)"), ('school', "School / sports fitness"),
        ('rest', "Rest / sick leave"), ('attendance', "Attendance"), ('glasses_use', "Use of glasses"),
        ('other', "Other"),
    ], string="Type", default='visual_fitness', required=True)
    rest_days = fields.Integer(string="Rest Days")
    body = fields.Html(string="Text", sanitize=True)
    state = fields.Selection([('draft', "Draft"), ('issued', "Issued")], default='draft', required=True, tracking=True)

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = f'/my/ophthalmology/certificates/{rec.id}'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('oph.certificate') or _("New")
        certificates = super().create(vals_list)
        for rec in certificates.filtered(lambda c: not c.body):
            rec.body = rec._default_body()
        return certificates

    def write(self, vals):
        if any(rec.state == 'issued' for rec in self) and set(vals) - {'state', 'message_main_attachment_id', 'access_token'}:
            raise UserError(_("An issued certificate cannot be modified."))
        return super().write(vals)

    @api.onchange('certificate_type', 'patient_id', 'exam_id', 'rest_days')
    def _onchange_certificate_type(self):
        if self.patient_id and self.state == 'draft':
            self.body = self._default_body()

    @api.model
    def _va_label(self, value):
        return VA_LABELS.get(value, value or '-')

    def _default_body(self):
        patient = self.patient_id
        lang = patient.lang or self.env.lang
        date = format_date(self.env, self.date or fields.Date.context_today(self), lang_code=lang)
        name = patient.name or ''
        document = patient.oph_document or '-'
        exam = self.exam_id
        if self.certificate_type == 'visual_fitness':
            va_od = self._va_label(exam.rx_va_od or exam.va_cc_od or exam.va_sc_od) if exam else '-'
            va_os = self._va_label(exam.rx_va_os or exam.va_cc_os or exam.va_sc_os) if exam else '-'
            text = _("I certify that %(name)s, ID %(doc)s, was examined on %(date)s. Visual acuity: right eye "
                     "%(od)s, left eye %(os)s. Visual field and color vision within normal limits. "
                     "The patient is FIT from the visual point of view to drive vehicles%(glasses)s.",
                     name=name, doc=document, date=date, od=va_od, os=va_os,
                     glasses=_(", using his/her optical correction") if exam and (exam.rx_sph_od or exam.rx_sph_os or exam.rx_cyl_od or exam.rx_cyl_os) else '')
        elif self.certificate_type == 'school':
            text = _("I certify that %(name)s, ID %(doc)s, was examined on %(date)s and presents no ophthalmological "
                     "contraindication for school and sports activities.", name=name, doc=document, date=date)
        elif self.certificate_type == 'rest':
            text = _("I certify that %(name)s, ID %(doc)s, was attended on %(date)s and requires %(days)s days of "
                     "rest from that date for ophthalmological reasons.", name=name, doc=document, date=date,
                     days=self.rest_days or 1)
        elif self.certificate_type == 'attendance':
            text = _("I certify that %(name)s, ID %(doc)s, attended an ophthalmological consultation on %(date)s.",
                     name=name, doc=document, date=date)
        elif self.certificate_type == 'glasses_use':
            text = _("I certify that %(name)s, ID %(doc)s, examined on %(date)s, must use his/her optical "
                     "correction permanently.", name=name, doc=document, date=date)
        else:
            text = _("I certify that %(name)s, ID %(doc)s, was examined on %(date)s.", name=name, doc=document, date=date)
        return Markup('<p>%s</p>') % text

    def action_issue(self):
        for rec in self:
            if not rec.doctor_id.oph_license:
                raise UserError(_("Set the professional license of %s (user preferences) before issuing.",
                                  rec.doctor_id.name))
        self.write({'state': 'issued'})

    def action_print(self):
        return self.env.ref('odossey_ophthalmology.action_report_certificate').report_action(self)

    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s - %s' % (self.name, self.patient_id.name)
