from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .oph_master import EYE_SELECTION

LOCKED_STUDY_FIELDS = {'study_type_id', 'eye', 'patient_id', 'report', 'conclusion', 'result_od', 'result_os'}


class OphStudy(models.Model):
    _name = 'oph.study'
    _description = 'Complementary Study'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string="Reference", required=True, readonly=True, copy=False, default=lambda self: _("New"))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    patient_id = fields.Many2one('res.partner', string="Patient", required=True, index=True, ondelete='restrict',
                                 domain="[('is_oph_patient', '=', True)]", tracking=True)
    exam_id = fields.Many2one('oph.exam', string="Requested in Exam", index='btree_not_null', ondelete='set null')
    study_type_id = fields.Many2one('oph.study.type', string="Study", required=True, tracking=True)
    kind = fields.Selection(related='study_type_id.kind')
    eye = fields.Selection(EYE_SELECTION, default='ou', required=True)
    date = fields.Datetime(string="Date", default=fields.Datetime.now)
    requested_by_id = fields.Many2one('res.users', string="Requested By", default=lambda self: self.env.user)
    technician_id = fields.Many2one('res.users', string="Performed By", domain="[('oph_is_technician', '=', True)]")
    reported_by_id = fields.Many2one('res.users', string="Reported By", domain="[('oph_is_ophthalmologist', '=', True)]")
    insurance_id = fields.Many2one('oph.insurance', string="Health Insurance")
    authorization = fields.Char(string="Authorization")
    state = fields.Selection([
        ('requested', "Requested"), ('scheduled', "Scheduled"), ('done', "Performed"), ('reported', "Reported"),
        ('cancel', "Cancelled"),
    ], default='requested', required=True, tracking=True, copy=False)
    # structured results per eye
    result_od = fields.Char(string="Result OD", help="Short result of the right eye.")
    result_os = fields.Char(string="Result OS")
    cmt_od = fields.Integer(string="Central Macular Thickness OD (µm)", aggregator=False)
    cmt_os = fields.Integer(string="Central Macular Thickness OS (µm)", aggregator=False)
    rnfl_od = fields.Integer(string="Average RNFL OD (µm)", aggregator=False, help="Retinal nerve fiber layer.")
    rnfl_os = fields.Integer(string="Average RNFL OS (µm)", aggregator=False)
    md_od = fields.Float(string="MD OD (dB)", digits=(4, 2), aggregator=False, help="Mean deviation of the visual field.")
    md_os = fields.Float(string="MD OS (dB)", digits=(4, 2), aggregator=False)
    psd_od = fields.Float(string="PSD OD (dB)", digits=(4, 2), aggregator=False)
    psd_os = fields.Float(string="PSD OS (dB)", digits=(4, 2), aggregator=False)
    vfi_od = fields.Integer(string="VFI OD (%)", aggregator=False)
    vfi_os = fields.Integer(string="VFI OS (%)", aggregator=False)
    axial_length_od = fields.Float(string="Axial Length OD (mm)", digits=(4, 2), aggregator=False)
    axial_length_os = fields.Float(string="Axial Length OS (mm)", digits=(4, 2), aggregator=False)
    acd_od = fields.Float(string="ACD OD (mm)", digits=(4, 2), aggregator=False, help="Anterior chamber depth.")
    acd_os = fields.Float(string="ACD OS (mm)", digits=(4, 2), aggregator=False)
    iol_power_od = fields.Float(string="IOL Power OD (D)", digits=(4, 2), aggregator=False,
                                help="Lens power calculated for the target refraction.")
    iol_power_os = fields.Float(string="IOL Power OS (D)", digits=(4, 2), aggregator=False)
    iol_formula = fields.Selection([('srk_t', "SRK/T"), ('barrett', "Barrett Universal II"), ('haigis', "Haigis"),
                                    ('hoffer_q', "Hoffer Q"), ('holladay', "Holladay"), ('kane', "Kane")],
                                   string="IOL Formula")
    target_refraction = fields.Float(string="Target Refraction (D)", digits=(4, 2), aggregator=False)
    pachymetry_od = fields.Integer(string="Pachymetry OD (µm)", aggregator=False)
    pachymetry_os = fields.Integer(string="Pachymetry OS (µm)", aggregator=False)
    cell_density_od = fields.Integer(string="Endothelial Cells OD (cells/mm²)", aggregator=False)
    cell_density_os = fields.Integer(string="Endothelial Cells OS (cells/mm²)", aggregator=False)
    kmax_od = fields.Float(string="Kmax OD (D)", digits=(4, 2), aggregator=False)
    kmax_os = fields.Float(string="Kmax OS (D)", digits=(4, 2), aggregator=False)
    report = fields.Html(sanitize=True, help="Report of the study written by the ophthalmologist.")
    conclusion = fields.Char()
    attachment_ids = fields.Many2many('ir.attachment', string="Device Files",
                                      help="PDF or images exported by the device (OCT, visual field, topographer).")
    line_ids = fields.One2many('oph.charge', 'study_id', string="Charges")
    claim_ids = fields.One2many('oph.insurance.claim', 'study_id', string="Insurance Services")

    def _compute_access_url(self):
        super()._compute_access_url()
        for study in self:
            study.access_url = f'/my/ophthalmology/studies/{study.id}'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('oph.study') or _("New")
            exam = self.env['oph.exam'].browse(vals.get('exam_id'))
            if exam and not vals.get('patient_id'):
                vals['patient_id'] = exam.patient_id.id
            if 'insurance_id' not in vals and vals.get('patient_id'):
                vals['insurance_id'] = self.env['res.partner'].browse(vals['patient_id']).oph_insurance_id.id
        studies = super().create(vals_list)
        for study in studies.filtered(lambda s: not s.report and s.study_type_id.report_template):
            study.report = study.study_type_id.report_template
        return studies

    def write(self, vals):
        if LOCKED_STUDY_FIELDS & set(vals) and not self.env.context.get('oph_allow_closed_edit') \
                and any(study.state == 'reported' for study in self):
            raise UserError(_("A reported study cannot be modified."))
        return super().write(vals)

    @api.onchange('study_type_id')
    def _onchange_study_type_id(self):
        if self.study_type_id.report_template and not self.report:
            self.report = self.study_type_id.report_template

    def action_schedule(self):
        self.filtered(lambda s: s.state == 'requested').write({'state': 'scheduled'})

    def action_done(self):
        for study in self:
            if study.state not in ('requested', 'scheduled'):
                continue
            vals = {'state': 'done'}
            if not study.technician_id and self.env.user.oph_is_technician:
                vals['technician_id'] = self.env.user.id
            study.write(vals)
            if not study.line_ids and study.study_type_id.product_id:
                study.line_ids = [(0, 0, {'product_id': study.study_type_id.product_id.id, 'quantity': 1})]
            if not study.exam_id or study.exam_id.state == 'done':
                study.line_ids._oph_bill(study.patient_id, study.insurance_id, study.patient_id.oph_plan_id,
                                         study.authorization, origin=study)

    def action_report(self):
        for study in self:
            if study.state not in ('done', 'scheduled', 'requested'):
                continue
            if not study.report and not study.conclusion:
                raise UserError(_("Write the report or the conclusion of the study first."))
            if study.state != 'done':
                study.action_done()
            study.write({'state': 'reported', 'reported_by_id': (study.reported_by_id or self.env.user).id})

    def action_cancel(self):
        if any(study.state == 'reported' for study in self):
            raise UserError(_("A reported study cannot be cancelled."))
        self.write({'state': 'cancel'})

    def action_print(self):
        return self.env.ref('odossey_ophthalmology.action_report_study').report_action(self)

    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s - %s' % (self.name, self.study_type_id.name or '')
