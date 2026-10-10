from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

VET_KINDS = [
    ('medication', "Medication"),
    ('vaccine', "Vaccine"),
    ('antiparasitic', "Antiparasitic"),
    ('food', "Food"),
    ('supply', "Clinical supply"),
    ('retail', "Pet shop item"),
    ('service', "Veterinary service"),
]

PREVENTIVE_GROUPS = [
    ('canine_polyvalent', "Canine polyvalent (distemper, parvo...)"),
    ('canine_puppy', "Puppy first vaccine (distemper + parvo)"),
    ('rabies', "Rabies"),
    ('kennel_cough', "Kennel cough"),
    ('leishmania', "Leishmaniasis"),
    ('leptospirosis', "Leptospirosis"),
    ('feline_polyvalent', "Feline triple / quadruple"),
    ('felv', "Feline leukaemia (FeLV)"),
    ('internal_parasites', "Internal parasites (deworming)"),
    ('external_parasites', "External parasites (fleas, ticks)"),
    ('heartworm', "Heartworm prevention"),
    ('other', "Other"),
]


class VetMedicationCategory(models.Model):
    _name = 'vet.medication.category'
    _description = 'Medication Category'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char()


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    vet_kind = fields.Selection(VET_KINDS, string="Veterinary Type",
                                help="Classifies the product for the veterinary workflows: vaccines and antiparasitics "
                                     "create preventive records with reminders, medications can be prescribed.")
    vet_species_ids = fields.Many2many('vet.species', string="Target Species")
    vet_laboratory = fields.Char(string="Laboratory", help="Manufacturer / laboratory (e.g. Holliday-Scott, Zoetis, MSD).")
    vet_active_ingredient = fields.Char(string="Active Ingredient", translate=True)
    vet_presentation = fields.Char(string="Presentation", translate=True, help="Pharmaceutical form: tablet, injectable, pipette, suspension...")
    vet_concentration = fields.Char(string="Concentration")
    vet_category_id = fields.Many2one('vet.medication.category', string="Therapeutic Category")
    vet_sale_condition = fields.Selection([
        ('otc', "Over the counter"),
        ('prescription', "Prescription"),
        ('archived', "Archived prescription"),
        ('vet_only', "Veterinary use only"),
    ], string="Sale Condition",
        help="Archived prescription = psychotropic / narcotic products: the prescription is kept by the pharmacy "
             "and the use is recorded in the controlled drugs register.")
    vet_controlled = fields.Boolean(string="Controlled Drug",
                                    help="Psychotropic or narcotic (ketamine, diazepam, opioids...). Prescriptions must be "
                                         "'archived' and every use appears in the controlled drugs register.")
    vet_registration = fields.Char(string="Health Registration No.",
                                   help="Official registration number (SENASA in Argentina, AIC in Italy).")
    vet_dose = fields.Char(string="Reference Dose", help="Orientative dose, e.g. '12.5-25 mg/kg every 12 h PO'. Always confirmed by the veterinarian.")
    vet_route = fields.Selection([
        ('po', "Oral (PO)"), ('sc', "Subcutaneous (SC)"), ('im', "Intramuscular (IM)"), ('iv', "Intravenous (IV)"),
        ('topical', "Topical"), ('spot_on', "Spot-on"), ('ophthalmic', "Ophthalmic"), ('otic', "Otic"),
        ('intranasal', "Intranasal"), ('inhaled', "Inhaled"), ('other', "Other"),
    ], string="Route")
    # preventive care (vaccines and antiparasitics)
    vet_preventive_group = fields.Selection(PREVENTIVE_GROUPS, string="Preventive Group",
                                            help="Products of the same group replace each other in the patient's plan: "
                                                 "a new dose closes the previous one and sets the next due date.")
    vet_disease_ids = fields.Many2many('vet.disease', string="Protects Against")
    vet_min_age_weeks = fields.Integer(string="Minimum Age (weeks)")
    vet_initial_doses = fields.Integer(string="Initial Doses", default=1,
                                       help="Number of doses of the primary course (e.g. 3 for a puppy polyvalent vaccine).")
    vet_dose_interval_weeks = fields.Integer(string="Interval Between Doses (weeks)", default=3)
    vet_booster_months = fields.Integer(string="Booster Every (months)", default=12,
                                        help="Months until the next booster once the primary course is complete.")
    vet_repeat_days = fields.Integer(string="Repeat Every (days)",
                                     help="For antiparasitics: days until the next application (e.g. 30, 90).")
    vet_mandatory = fields.Boolean(string="Mandatory by Law", help="e.g. rabies vaccination (Argentina, Law 22.953).")
    # services
    vet_duration = fields.Integer(string="Duration (min)", help="Typical duration of the service, used for appointments.")
    vet_size_surcharge = fields.Boolean(string="Price by Size", help="The price usually varies with the size of the animal.")

    @api.onchange('vet_kind')
    def _onchange_vet_kind(self):
        if self.vet_kind == 'service':
            self.type = 'service'
        elif self.vet_kind in ('medication', 'vaccine', 'antiparasitic', 'food', 'supply', 'retail') and self.type == 'service':
            self.type = 'consu'
        if self.vet_kind == 'antiparasitic' and not self.vet_repeat_days:
            self.vet_repeat_days = 30

    @api.onchange('vet_controlled')
    def _onchange_vet_controlled(self):
        if self.vet_controlled:
            self.vet_sale_condition = 'archived'

    @api.constrains('vet_controlled', 'vet_sale_condition')
    def _check_vet_controlled(self):
        for product in self:
            if product.vet_controlled and product.vet_sale_condition not in ('archived', 'vet_only'):
                raise ValidationError(_("%s is a controlled drug: its sale condition must be 'Archived prescription' or "
                                        "'Veterinary use only'.", product.display_name))
