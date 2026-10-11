from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class VetAlert(models.Model):
    _name = 'vet.alert'
    _description = 'Patient Alert'
    _order = 'severity desc, name'

    name = fields.Char(required=True, translate=True)
    severity = fields.Selection([
        ('info', "Information"), ('warning', "Warning"), ('danger', "Danger"),
    ], default='warning', required=True,
        help="Danger alerts (aggressive, severe allergy...) are shown in red on every screen of the patient.")
    category = fields.Selection([
        ('behaviour', "Behaviour / handling"), ('allergy', "Allergy"), ('medical', "Medical condition"), ('other', "Other"),
    ], default='other', required=True)
    color = fields.Integer(compute='_compute_color')
    active = fields.Boolean(default=True)

    @api.depends('severity')
    def _compute_color(self):
        colors = {'info': 4, 'warning': 2, 'danger': 1}
        for alert in self:
            alert.color = colors.get(alert.severity, 0)


class VetPet(models.Model):
    _name = 'vet.pet'
    _description = 'Patient (Pet)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = 'name'
    _rec_names_search = ['name', 'ref', 'microchip', 'owner_id']

    name = fields.Char(required=True, tracking=True)
    ref = fields.Char(string="Record No.", readonly=True, copy=False, default=lambda self: _("New"),
                      help="Clinical record number, assigned automatically.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    owner_id = fields.Many2one('res.partner', string="Owner", required=True, tracking=True, index=True,
                               help="Person responsible for the animal (tutor). Receives reminders and invoices.")
    owner_phone = fields.Char(related='owner_id.phone', string="Owner Phone")
    owner_email = fields.Char(related='owner_id.email', string="Owner Email")
    species_id = fields.Many2one('vet.species', required=True, tracking=True)
    breed_id = fields.Many2one('vet.breed', tracking=True, domain="[('species_id', '=', species_id)]")
    sex = fields.Selection([('male', "Male"), ('female', "Female"), ('unknown', "Unknown")],
                           default='unknown', required=True, tracking=True)
    neutered = fields.Boolean(string="Neutered / Spayed", tracking=True)
    neutered_date = fields.Date(string="Neutering Date")
    birthdate = fields.Date(tracking=True)
    birthdate_estimated = fields.Boolean(string="Estimated Birthdate",
                                         help="Tick when the date of birth is an estimate (rescued or adopted animals).")
    age = fields.Char(compute='_compute_age', help="Age computed from the date of birth.")
    age_months = fields.Integer(compute='_compute_age')
    coat = fields.Char(string="Coat / Colour")
    size = fields.Selection(related='breed_id.size', string="Breed Size")
    microchip = fields.Char(tracking=True, copy=False,
                            help="15-digit ISO 11784/11785 transponder number.")
    tattoo = fields.Char(copy=False)
    pedigree = fields.Char(string="Pedigree / Passport No.", copy=False)
    blood_type = fields.Char()
    insurance = fields.Char(string="Insurance / Health Plan")
    temperament = fields.Selection([
        ('calm', "Calm"), ('nervous', "Nervous"), ('fearful', "Fearful"), ('aggressive', "Aggressive"),
    ], default='calm', tracking=True, help="How the patient usually behaves in the clinic.")
    handling_notes = fields.Text(help="Instructions for staff: muzzle, sedation before handling, treats that calm it...")
    alert_ids = fields.Many2many('vet.alert', string="Alerts")
    has_danger_alert = fields.Boolean(compute='_compute_has_danger_alert', store=True)
    alert_summary = fields.Char(compute='_compute_alert_summary')
    allergy_notes = fields.Text(string="Allergies", tracking=True)
    chronic_condition_ids = fields.Many2many('vet.disease', string="Chronic Conditions")
    diet = fields.Char(help="Food the patient usually eats.")
    note = fields.Html(string="Notes")
    deceased = fields.Boolean(tracking=True)
    date_of_death = fields.Date()
    cause_of_death = fields.Char()

    weight_ids = fields.One2many('vet.weight', 'pet_id', string="Weight History")
    weight = fields.Float(aggregator=False, string="Current Weight (kg)", compute='_compute_weight', store=True, digits=(16, 2))
    weight_date = fields.Date(string="Weighed On", compute='_compute_weight', store=True)

    _microchip_unique = models.Constraint('unique(microchip, company_id)', "Another patient already has this microchip number.")

    @api.depends('birthdate')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for pet in self:
            if not pet.birthdate or pet.birthdate > today:
                pet.age, pet.age_months = False, 0
                continue
            end = pet.date_of_death if pet.deceased and pet.date_of_death else today
            delta = relativedelta(end, pet.birthdate)
            pet.age_months = delta.years * 12 + delta.months
            if delta.years:
                pet.age = _("%(y)s y %(m)s m", y=delta.years, m=delta.months)
            elif delta.months:
                pet.age = _("%(m)s months", m=delta.months)
            else:
                pet.age = _("%(d)s days", d=delta.days)

    @api.depends('weight_ids.weight', 'weight_ids.date')
    def _compute_weight(self):
        for pet in self:
            last = pet.weight_ids.sorted(lambda w: (w.date, w.id))[-1:]
            pet.weight = last.weight
            pet.weight_date = last.date

    @api.depends('alert_ids', 'alert_ids.severity', 'temperament')
    def _compute_has_danger_alert(self):
        for pet in self:
            pet.has_danger_alert = pet.temperament == 'aggressive' or any(a.severity == 'danger' for a in pet.alert_ids)

    @api.depends('alert_ids', 'temperament')
    def _compute_alert_summary(self):
        for pet in self:
            names = pet.alert_ids.mapped('name')
            if pet.temperament == 'aggressive':
                names.insert(0, dict(self._fields['temperament']._description_selection(self.env))['aggressive'])
            pet.alert_summary = ' · '.join(names)

    @api.onchange('species_id')
    def _onchange_species_id(self):
        if self.breed_id and self.breed_id.species_id != self.species_id:
            self.breed_id = False

    @api.constrains('birthdate', 'date_of_death')
    def _check_dates(self):
        today = fields.Date.context_today(self)
        for pet in self:
            if pet.birthdate and pet.birthdate > today:
                raise ValidationError(_("The date of birth of %s is in the future.", pet.name))
            if pet.birthdate and pet.date_of_death and pet.date_of_death < pet.birthdate:
                raise ValidationError(_("The date of death of %s is before its date of birth.", pet.name))

    @api.constrains('microchip')
    def _check_microchip(self):
        for pet in self:
            chip = (pet.microchip or '').replace(' ', '')
            if chip and (not chip.isdigit() or len(chip) != 15):
                raise ValidationError(_("The microchip number must have 15 digits (ISO 11784/11785)."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('ref') or vals['ref'] == _("New"):
                vals['ref'] = self.env['ir.sequence'].next_by_code('vet.pet') or _("New")
            if vals.get('microchip'):
                vals['microchip'] = vals['microchip'].replace(' ', '')
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('microchip'):
            vals['microchip'] = vals['microchip'].replace(' ', '')
        if vals.get('deceased'):
            vals.setdefault('date_of_death', fields.Date.context_today(self))
        return super().write(vals)

    @api.depends('name', 'owner_id', 'species_id')
    def _compute_display_name(self):
        for pet in self:
            if self.env.context.get('vet_pet_short_name'):
                pet.display_name = pet.name
                continue
            owner = pet.owner_id.name
            pet.display_name = "%s (%s)" % (pet.name, owner) if owner else pet.name


class VetWeight(models.Model):
    _name = 'vet.weight'
    _description = 'Weight Record'
    _order = 'date desc, id desc'

    pet_id = fields.Many2one('vet.pet', required=True, ondelete='cascade', index=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    weight = fields.Float(aggregator=False, string="Weight (kg)", required=True, digits=(16, 2))
    body_condition = fields.Selection([(str(i), str(i)) for i in range(1, 10)], string="Body Condition (1-9)",
                                      help="Body condition score on the 9-point scale (WSAVA): 4-5 is ideal.")
    note = fields.Char()

    @api.constrains('weight')
    def _check_weight(self):
        for rec in self:
            if rec.weight <= 0:
                raise ValidationError(_("The weight must be greater than zero."))
