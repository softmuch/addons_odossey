from odoo import api, fields, models

EYE_SELECTION = [('od', "Right eye (OD)"), ('os', "Left eye (OS)"), ('ou', "Both eyes (OU)")]


class OphDiagnosis(models.Model):
    _name = 'oph.diagnosis'
    _description = 'Eye Diagnosis (ICD-10)'
    _order = 'code, name'
    _rec_names_search = ['code', 'name']

    code = fields.Char(string="ICD-10 Code", required=True, index=True,
                       help="ICD-10 code (chapter VII, H00-H59). Example: H40.1 for primary open-angle glaucoma.")
    name = fields.Char(required=True, translate=True)
    group = fields.Selection([
        ('lids', "Eyelids, lacrimal system and orbit"), ('conjunctiva', "Conjunctiva"),
        ('cornea', "Sclera, cornea, iris and ciliary body"), ('lens', "Lens"), ('retina', "Choroid and retina"),
        ('glaucoma', "Glaucoma"), ('vitreous', "Vitreous body and globe"), ('nerve', "Optic nerve and visual pathways"),
        ('motility', "Ocular muscles, binocular movement, accommodation and refraction"),
        ('vision', "Visual disturbances and blindness"), ('other', "Other"),
    ], default='other', required=True)
    chronic = fields.Boolean(help="Chronic disease that needs periodic controls (e.g. glaucoma, diabetic retinopathy).")
    control_months = fields.Integer(string="Control Every (months)",
                                    help="Suggested interval for the next control when this diagnosis is recorded. "
                                         "Example: 4 for glaucoma under treatment.")
    active = fields.Boolean(default=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for diagnosis in self:
            diagnosis.display_name = '%s %s' % (diagnosis.code or '', diagnosis.name or '')


class OphAllergy(models.Model):
    _name = 'oph.allergy'
    _description = 'Allergy'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    severity = fields.Selection([('info', "Info"), ('warning', "Warning"), ('danger', "Danger")],
                                default='warning', required=True)
    active = fields.Boolean(default=True)


class OphStudyType(models.Model):
    _name = 'oph.study.type'
    _description = 'Complementary Study Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help="Internal or nomenclator code of the study.")
    sequence = fields.Integer(default=10)
    kind = fields.Selection([
        ('oct', "OCT"), ('visual_field', "Visual field"), ('biometry', "Biometry"), ('topography', "Topography"),
        ('pachymetry', "Pachymetry"), ('imaging', "Retinography / angiography"), ('ultrasound', "Ultrasound"),
        ('endothelial', "Specular microscopy"), ('other', "Other"),
    ], default='other', required=True,
        help="Decides which result fields are shown on the study. Example: Visual field → MD, PSD and VFI.")
    duration = fields.Integer(string="Duration (min)", default=20)
    product_id = fields.Many2one('product.product', string="Service", help="Service charged when the study is done.")
    report_template = fields.Html(translate=True, sanitize=True,
                                  help="Text used to start the report of the study.")
    active = fields.Boolean(default=True)


class OphProcedure(models.Model):
    _name = 'oph.procedure'
    _description = 'Surgical Procedure'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help="Internal or nomenclator code of the procedure.")
    sequence = fields.Integer(default=10)
    kind = fields.Selection([
        ('cataract', "Cataract"), ('refractive', "Refractive"), ('intravitreal', "Intravitreal injection"),
        ('glaucoma', "Glaucoma"), ('retina', "Retina / vitreous"), ('cornea', "Cornea"),
        ('oculoplastic', "Oculoplastic"), ('strabismus', "Strabismus"), ('laser', "Laser"), ('other', "Other"),
    ], default='other', required=True)
    duration = fields.Integer(string="Duration (min)", default=30, required=True)
    anesthesia = fields.Selection([
        ('topical', "Topical"), ('local', "Local (peribulbar / retrobulbar)"), ('sedation', "Sedation"),
        ('general', "General"),
    ], default='topical')
    requires_iol = fields.Boolean(string="Requires Intraocular Lens")
    product_id = fields.Many2one('product.product', string="Service", help="Surgical fee charged for the procedure.")
    consent_template_id = fields.Many2one('oph.consent.template', string="Consent Template")
    postop_days = fields.Char(string="Post-op Controls (days)", default="1,7,30",
                              help="Days after the surgery when a control appointment is booked, separated by commas. "
                                   "Example: 1,7,30 → controls the next day, after one week and after one month.")
    active = fields.Boolean(default=True)

    def _postop_day_list(self):
        self.ensure_one()
        days = []
        for part in (self.postop_days or '').split(','):
            part = part.strip()
            if part.isdigit():
                days.append(int(part))
        return sorted(set(days))


class OphAppointmentType(models.Model):
    _name = 'oph.appointment.type'
    _description = 'Appointment Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    duration = fields.Integer(string="Duration (min)", default=20, required=True)
    visit_type = fields.Selection([
        ('first', "First visit"), ('control', "Control"), ('postop', "Post-operative"), ('emergency', "Emergency"),
        ('study', "Studies"), ('pediatric', "Pediatrics / orthoptics"), ('contact_lens', "Contact lenses"),
        ('surgery', "Surgery"),
    ], default='first', required=True)
    product_id = fields.Many2one('product.product', string="Service", help="Service charged for this kind of visit.")
    study_type_id = fields.Many2one('oph.study.type', string="Study",
                                    help="For study appointments: the study requested when the patient arrives.")
    color = fields.Integer()
    active = fields.Boolean(default=True)


class OphRoom(models.Model):
    _name = 'oph.room'
    _description = 'Room / Operating Room'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    room_type = fields.Selection([
        ('consulting', "Consulting room"), ('pre_consultation', "Pre-consultation"), ('study', "Studies"),
        ('laser', "Laser room"), ('operating', "Operating room"), ('other', "Other"),
    ], default='consulting', required=True)
    active = fields.Boolean(default=True)
