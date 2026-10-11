from odoo import _, api, fields, models


class VetLabPanel(models.Model):
    _name = 'vet.lab.panel'
    _description = 'Laboratory Panel'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    sequence = fields.Integer(default=10)
    analyte_ids = fields.One2many('vet.lab.analyte', 'panel_id', string="Analytes")
    product_id = fields.Many2one('product.product', string="Service", help="Service charged when the panel is requested.")
    active = fields.Boolean(default=True)


class VetLabAnalyte(models.Model):
    _name = 'vet.lab.analyte'
    _description = 'Laboratory Analyte'
    _order = 'panel_id, sequence, id'

    panel_id = fields.Many2one('vet.lab.panel', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
    unit = fields.Char()
    dog_min = fields.Float(string="Dog Min", digits=(16, 3))
    dog_max = fields.Float(string="Dog Max", digits=(16, 3))
    cat_min = fields.Float(string="Cat Min", digits=(16, 3))
    cat_max = fields.Float(string="Cat Max", digits=(16, 3))
    qualitative = fields.Boolean(help="Result is a text (positive / negative...) instead of a number.")


class VetLabResult(models.Model):
    _name = 'vet.lab.result'
    _description = 'Laboratory Result'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string="Reference", readonly=True, copy=False, default=lambda self: _("New"))
    pet_id = fields.Many2one('vet.pet', string="Patient", required=True, index=True)
    owner_id = fields.Many2one(related='pet_id.owner_id', store=True)
    species_id = fields.Many2one(related='pet_id.species_id')
    consultation_id = fields.Many2one('vet.consultation', string="Consultation", index=True)
    panel_id = fields.Many2one('vet.lab.panel', string="Panel", required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    laboratory = fields.Char(string="Performed By", help="In-house analyser or external laboratory.")
    state = fields.Selection([('requested', "Requested"), ('done', "Results Received")], default='requested', tracking=True)
    line_ids = fields.One2many('vet.lab.result.line', 'result_id', string="Results", copy=True)
    abnormal_count = fields.Integer(compute='_compute_abnormal_count')
    conclusion = fields.Text()
    attachment_ids = fields.Many2many('ir.attachment', string="Report Files")

    @api.depends('line_ids.flag')
    def _compute_abnormal_count(self):
        for rec in self:
            rec.abnormal_count = len(rec.line_ids.filtered(lambda l: l.flag in ('low', 'high')))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('vet.lab.result') or _("New")
        records = super().create(vals_list)
        for rec in records.filtered(lambda r: not r.line_ids):
            rec._fill_lines()
        return records

    @api.onchange('panel_id')
    def _onchange_panel_id(self):
        if self.panel_id:
            self.line_ids = [(5, 0, 0)] + [(0, 0, {'analyte_id': a.id}) for a in self.panel_id.analyte_ids]

    def _fill_lines(self):
        for rec in self:
            rec.line_ids = [(0, 0, {'analyte_id': a.id}) for a in rec.panel_id.analyte_ids]

    def action_done(self):
        self.write({'state': 'done'})

    def action_print(self):
        return self.env.ref('odossey_veterinary.action_report_lab_result').report_action(self)


class VetLabResultLine(models.Model):
    _name = 'vet.lab.result.line'
    _description = 'Laboratory Result Line'
    _order = 'result_id, sequence, id'

    result_id = fields.Many2one('vet.lab.result', required=True, ondelete='cascade')
    sequence = fields.Integer(related='analyte_id.sequence', store=True)
    analyte_id = fields.Many2one('vet.lab.analyte', required=True)
    unit = fields.Char(related='analyte_id.unit')
    value = fields.Float(aggregator=False, digits=(16, 3))
    value_text = fields.Char(string="Text Result")
    ref_min = fields.Float(compute='_compute_ref', digits=(16, 3))
    ref_max = fields.Float(compute='_compute_ref', digits=(16, 3))
    reference = fields.Char(compute='_compute_ref')
    flag = fields.Selection([('normal', "Normal"), ('low', "Low"), ('high', "High")], compute='_compute_flag', store=True)

    def _ref_range(self):
        self.ensure_one()
        analyte = self.analyte_id
        if self.result_id.pet_id.species_id.code == 'CAT':
            return analyte.cat_min, analyte.cat_max
        return analyte.dog_min, analyte.dog_max

    @api.depends('analyte_id', 'result_id.species_id')
    def _compute_ref(self):
        for line in self:
            lo, hi = line._ref_range()
            line.ref_min, line.ref_max = lo, hi
            line.reference = '%s - %s' % (line._vet_format_number(lo), line._vet_format_number(hi)) if (lo or hi) else ''

    def _vet_format_number(self, value):
        """Number in the user's language without trailing zeros: 38 / 1,025 / 7,5 (es) or 7.5 (en)."""
        lang = self.env['res.lang']._get_data(code=self.env.lang or 'en_US')
        text = ('%.3f' % value).rstrip('0').rstrip('.')
        return text.replace('.', lang.decimal_point or '.')

    def _vet_value_display(self):
        self.ensure_one()
        return self._vet_format_number(self.value)

    @api.depends('value', 'value_text', 'analyte_id', 'result_id.species_id')
    def _compute_flag(self):
        for line in self:
            analyte = line.analyte_id
            lo, hi = line._ref_range()
            if analyte.qualitative or not (lo or hi) or (not line.value and not line.value_text):
                line.flag = False
            elif line.value < lo:
                line.flag = 'low'
            elif hi and line.value > hi:
                line.flag = 'high'
            else:
                line.flag = 'normal'


class VetCertificate(models.Model):
    _name = 'vet.certificate'
    _description = 'Veterinary Certificate'
    _inherit = ['mail.thread', 'portal.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string="Number", readonly=True, copy=False, default=lambda self: _("New"))
    certificate_type = fields.Selection([
        ('health', "Health certificate"),
        ('travel', "Health certificate for travel"),
        ('deworming', "Deworming certificate"),
        ('neutering', "Neutering certificate"),
        ('death', "Death certificate"),
        ('other', "Other"),
    ], string="Type", required=True, default='health')
    pet_id = fields.Many2one('vet.pet', string="Patient", required=True, index=True)
    owner_id = fields.Many2one(related='pet_id.owner_id', store=True)
    vet_id = fields.Many2one('res.users', string="Veterinarian", required=True, default=lambda self: self.env.user,
                             domain="[('vet_is_veterinarian', '=', True)]")
    date = fields.Date(required=True, default=fields.Date.context_today)
    valid_until = fields.Date(help="Argentina: the health and deworming certificates for a SENASA travel certificate (CVI) "
                                   "must be presented within 10 days of issue.")
    destination = fields.Char(help="Destination country / city (travel certificate).")
    body = fields.Html(string="Certificate Text")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.onchange('certificate_type', 'date', 'pet_id', 'destination')
    def _onchange_type(self):
        if self.certificate_type in ('travel', 'deworming') and self.date:
            self.valid_until = fields.Date.add(self.date, days=10)
        if self.pet_id and self.certificate_type:
            self.body = self._default_body()

    def _default_body(self):
        pet = self.pet_id
        texts = {
            'health': _("I certify that I have examined the animal described above and that, on the date of this examination, "
                        "it shows no clinical signs of infectious, contagious or parasitic disease and is in good general health."),
            'travel': _("I certify that I have examined the animal described above and that it is clinically healthy, shows no signs "
                        "of infectious or contagious disease, and is fit to travel to %(dest)s. Its rabies vaccination is valid.",
                        dest=self.destination or '...'),
            'deworming': _("I certify that the animal described above has been treated against internal and external parasites "
                           "on the date of this certificate."),
            'neutering': _("I certify that the animal described above has been surgically neutered."),
            'death': _("I certify the death of the animal described above."),
            'other': '',
        }
        return '<p>%s</p>' % texts.get(self.certificate_type, '') if pet else ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('vet.certificate') or _("New")
        records = super().create(vals_list)
        for rec in records.filtered(lambda r: not r.body):
            rec.body = rec._default_body()
        return records

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/my/vet/certificates/%s' % rec.id

    def action_print(self):
        return self.env.ref('odossey_veterinary.action_report_certificate').report_action(self)

    def _get_report_base_filename(self):
        self.ensure_one()
        return _("Certificate %s", self.name)


class VetPet(models.Model):
    _inherit = 'vet.pet'

    lab_result_ids = fields.One2many('vet.lab.result', 'pet_id')
    certificate_ids = fields.One2many('vet.certificate', 'pet_id')
