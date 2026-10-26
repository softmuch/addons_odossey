import hashlib

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .oph_master import EYE_SELECTION

ISSUED_WRITABLE = {'state', 'cuir', 'platform', 'message_main_attachment_id', 'access_token'}


class OphPrescription(models.Model):
    _name = 'oph.prescription'
    _description = 'Medication Prescription'
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
    diagnosis_id = fields.Many2one('oph.diagnosis', string="Diagnosis",
                                   help="Required on prescriptions (Law 27.553 and its regulations).")
    insurance_id = fields.Many2one('oph.insurance', string="Coverage")
    member_number = fields.Char(string="Member No.")
    line_ids = fields.One2many('oph.prescription.line', 'prescription_id', string="Medications")
    no_substitution = fields.Boolean(string="Do Not Substitute",
                                     help="The pharmacist may not replace the brand prescribed (must be justified).")
    notes = fields.Text(string="Indications")
    state = fields.Selection([('draft', "Draft"), ('issued', "Issued"), ('cancel', "Cancelled")],
                             default='draft', required=True, tracking=True, copy=False)
    cuir = fields.Char(string="Electronic Prescription No. (CUIR)", tracking=True, copy=False,
                       help="Unique code returned by the electronic prescription platform registered in ReNaPDiS "
                            "where the prescription was issued. Since 2025 only electronic prescriptions from a "
                            "registered platform are valid in Argentina.")
    platform = fields.Char(string="Prescription Platform", copy=False,
                           help="Registered platform used to issue the electronic prescription.")
    content_hash = fields.Char(string="Fingerprint", readonly=True, copy=False)

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = f'/my/ophthalmology/prescriptions/{rec.id}'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('oph.prescription') or _("New")
            if vals.get('patient_id') and 'insurance_id' not in vals:
                patient = self.env['res.partner'].browse(vals['patient_id'])
                vals['insurance_id'] = patient.oph_insurance_id.id
                vals.setdefault('member_number', patient.oph_member_number)
        return super().create(vals_list)

    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        if self.patient_id:
            self.insurance_id = self.patient_id.oph_insurance_id
            self.member_number = self.patient_id.oph_member_number

    def write(self, vals):
        if set(vals) - ISSUED_WRITABLE and any(rec.state == 'issued' for rec in self):
            raise UserError(_("An issued prescription cannot be modified: cancel it and issue a new one."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state != 'draft' for rec in self):
            raise UserError(_("Only draft prescriptions can be deleted."))
        return super().unlink()

    def _content_string(self):
        self.ensure_one()
        parts = [self.name, str(self.date), self.patient_id.name or '', self.patient_id.oph_document or '',
                 self.doctor_id.name or '', self.doctor_id.oph_license or '', self.diagnosis_id.code or '']
        for line in self.line_ids:
            parts += [line.product_id.display_name or '', line.active_ingredient or '', line.eye or '',
                      line.posology or '', line.duration or '', str(line.quantity)]
        return '|'.join(parts)

    def action_issue(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.line_ids:
                raise UserError(_("Add at least one medication."))
            if not rec.doctor_id.oph_license:
                raise UserError(_("Set the professional license of %s (user preferences) before issuing.",
                                  rec.doctor_id.name))
            if not rec.diagnosis_id:
                raise UserError(_("The diagnosis is required on prescriptions."))
            rec.write({'state': 'issued', 'content_hash': hashlib.sha256(rec._content_string().encode()).hexdigest()})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_print(self):
        return self.env.ref('odossey_ophthalmology.action_report_prescription').report_action(self)

    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s - %s' % (self.name, self.patient_id.name)


class OphPrescriptionLine(models.Model):
    _name = 'oph.prescription.line'
    _description = 'Prescribed Medication'
    _order = 'sequence, id'

    prescription_id = fields.Many2one('oph.prescription', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', string="Medication", required=True,
                                 domain="[('oph_kind', '=', 'medication')]")
    active_ingredient = fields.Char(string="Generic Name", help="Generic name printed first (Law 25.649).")
    eye = fields.Selection(EYE_SELECTION, default='ou')
    posology = fields.Char(help="Example: 1 drop every 12 hours.")
    duration = fields.Char(help="Example: 7 days, chronic.")
    quantity = fields.Integer(string="Units", default=1)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.active_ingredient = self.product_id.oph_active_ingredient
            self.posology = self.product_id.oph_posology

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            product = self.env['product.product'].browse(vals.get('product_id'))
            if product:
                vals.setdefault('active_ingredient', product.oph_active_ingredient)
                vals.setdefault('posology', product.oph_posology)
        lines = super().create(vals_list)
        if any(line.prescription_id.state == 'issued' for line in lines):
            raise UserError(_("An issued prescription cannot be modified."))
        return lines

    def write(self, vals):
        if any(line.prescription_id.state == 'issued' for line in self):
            raise UserError(_("An issued prescription cannot be modified."))
        return super().write(vals)
