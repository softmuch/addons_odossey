import hashlib

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

ISSUED_WRITABLE = {'state', 'message_main_attachment_id', 'access_token'}


class OphGlassesPrescription(models.Model):
    _name = 'oph.glasses.prescription'
    _description = 'Glasses / Contact Lens Prescription'
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
    valid_until = fields.Date(compute='_compute_valid_until', store=True, readonly=False,
                              help="Opticians usually accept a prescription for 6 months.")
    prescription_type = fields.Selection([('glasses', "Glasses"), ('contact_lens', "Contact lenses")],
                                         default='glasses', required=True)
    lens_use = fields.Selection([
        ('distance', "Distance"), ('near', "Near / reading"), ('bifocal', "Bifocal"), ('progressive', "Progressive"),
        ('occupational', "Occupational"),
    ], default='distance', required=True)
    sph_od = fields.Float(string="Sphere OD", digits=(4, 2), aggregator=False)
    cyl_od = fields.Float(string="Cylinder OD", digits=(4, 2), aggregator=False)
    axis_od = fields.Integer(string="Axis OD", aggregator=False)
    add_od = fields.Float(string="Addition OD", digits=(4, 2), aggregator=False)
    prism_od = fields.Char(string="Prism OD", help="Example: 2Δ base in.")
    sph_os = fields.Float(string="Sphere OS", digits=(4, 2), aggregator=False)
    cyl_os = fields.Float(string="Cylinder OS", digits=(4, 2), aggregator=False)
    axis_os = fields.Integer(string="Axis OS", aggregator=False)
    add_os = fields.Float(string="Addition OS", digits=(4, 2), aggregator=False)
    prism_os = fields.Char(string="Prism OS")
    pd_distance = fields.Float(string="PD Distance (mm)", digits=(4, 1), aggregator=False)
    pd_near = fields.Float(string="PD Near (mm)", digits=(4, 1), aggregator=False)
    # contact lenses
    cl_brand = fields.Char(string="Lens Brand / Model")
    cl_base_curve_od = fields.Float(string="Base Curve OD (mm)", digits=(3, 2), aggregator=False)
    cl_base_curve_os = fields.Float(string="Base Curve OS (mm)", digits=(3, 2), aggregator=False)
    cl_diameter_od = fields.Float(string="Diameter OD (mm)", digits=(3, 1), aggregator=False)
    cl_diameter_os = fields.Float(string="Diameter OS (mm)", digits=(3, 1), aggregator=False)
    cl_replacement = fields.Selection([('daily', "Daily"), ('biweekly', "Two weeks"), ('monthly', "Monthly"),
                                       ('quarterly', "Quarterly"), ('yearly', "Yearly")], string="Replacement")
    lens_recommendations = fields.Char(string="Recommendations",
                                       help="Example: anti-reflective coating, photochromic, polycarbonate.")
    notes = fields.Text()
    state = fields.Selection([('draft', "Draft"), ('issued', "Issued"), ('cancel', "Cancelled")],
                             default='draft', required=True, tracking=True, copy=False)
    content_hash = fields.Char(string="Fingerprint", readonly=True, copy=False)

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = f'/my/ophthalmology/glasses/{rec.id}'

    @api.depends('date')
    def _compute_valid_until(self):
        for rec in self:
            rec.valid_until = rec.date + relativedelta(months=6) if rec.date else False

    @api.constrains('axis_od', 'axis_os', 'cyl_od', 'cyl_os')
    def _check_axis(self):
        for rec in self:
            for eye in ('od', 'os'):
                if not 0 <= rec['axis_%s' % eye] <= 180:
                    raise ValidationError(_("Axes must be between 0 and 180 degrees."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('oph.glasses.prescription') or _("New")
        return super().create(vals_list)

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
                 self.doctor_id.name or '', self.doctor_id.oph_license or '', self.prescription_type, self.lens_use]
        for eye in ('od', 'os'):
            parts += ['%.2f' % self['sph_%s' % eye], '%.2f' % self['cyl_%s' % eye], str(self['axis_%s' % eye]),
                      '%.2f' % self['add_%s' % eye], self['prism_%s' % eye] or '']
        parts += ['%.1f' % self.pd_distance, '%.1f' % self.pd_near]
        return '|'.join(parts)

    def action_issue(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.doctor_id.oph_license:
                raise UserError(_("Set the professional license of %s (user preferences) before issuing.",
                                  rec.doctor_id.name))
            if not any(rec['%s_%s' % (n, e)] for n in ('sph', 'cyl', 'add') for e in ('od', 'os')):
                raise UserError(_("The prescription has no values."))
            rec.write({'state': 'issued', 'content_hash': hashlib.sha256(rec._content_string().encode()).hexdigest()})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_print(self):
        return self.env.ref('odossey_ophthalmology.action_report_glasses').report_action(self)

    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s - %s' % (self.name, self.patient_id.name)

    @api.model
    def _format_diopter(self, value):
        if not value:
            return '0.00' if value == 0 else ''
        return '%+.2f' % value
