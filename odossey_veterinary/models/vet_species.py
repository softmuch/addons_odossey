from odoo import api, fields, models

# Faces shown in the agenda (static/src/img/species/<key>.svg, Microsoft Fluent Emoji, MIT)
SPECIES_ICONS = [
    ('dog', "Dog"), ('cat', "Cat"), ('rabbit', "Rabbit"), ('ferret', "Ferret"), ('hamster', "Hamster"),
    ('guinea_pig', "Guinea pig"), ('mouse', "Mouse"), ('rat', "Rat"), ('chinchilla', "Chinchilla"),
    ('canary', "Canary"), ('parrot', "Parrot"), ('budgerigar', "Budgerigar"), ('cockatiel', "Bird"),
    ('turtle', "Turtle"), ('lizard', "Lizard"), ('snake', "Snake"), ('horse', "Horse"), ('cattle', "Cow"),
    ('other', "Paw"),
]
SPECIES_ICON_KEYS = {key for key, _label in SPECIES_ICONS} | {'other_bird'}


class VetSpecies(models.Model):
    _name = 'vet.species'
    _description = 'Animal Species'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help="Short technical code, e.g. DOG, CAT.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    breed_ids = fields.One2many('vet.breed', 'species_id', string="Breeds")
    breed_count = fields.Integer(compute='_compute_breed_count')
    gestation_days = fields.Integer(help="Average gestation length in days (used as a reference in the medical record).")
    color = fields.Integer()
    icon = fields.Selection(SPECIES_ICONS, compute='_compute_icon', store=True, readonly=False,
                            help="Face shown next to the patient in the agenda. Example: Dog.")
    icon_url = fields.Char(compute='_compute_icon_url', string="Icon Preview")

    _code_unique = models.Constraint('unique(code)', "The species code must be unique.")

    @api.depends('code')
    def _compute_icon(self):
        for species in self:
            if not species.icon:
                code = (species.code or '').lower()
                species.icon = 'cockatiel' if code == 'other_bird' else code if code in SPECIES_ICON_KEYS else 'other'

    @api.depends('icon')
    def _compute_icon_url(self):
        for species in self:
            species.icon_url = '/odossey_veterinary/static/src/img/species/%s.svg' % (species.icon or 'other')

    def _compute_breed_count(self):
        for species in self:
            species.breed_count = len(species.breed_ids)


class VetBreed(models.Model):
    _name = 'vet.breed'
    _description = 'Animal Breed'
    _order = 'species_id, name'

    name = fields.Char(required=True, translate=True)
    species_id = fields.Many2one('vet.species', required=True, ondelete='cascade', index=True)
    size = fields.Selection([
        ('toy', "Toy"), ('small', "Small"), ('medium', "Medium"), ('large', "Large"), ('giant', "Giant"),
    ], help="Typical adult size; used to suggest services priced by size (neutering, grooming...).")
    active = fields.Boolean(default=True)
