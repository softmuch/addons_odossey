from odoo import fields, models


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

    _code_unique = models.Constraint('unique(code)', "The species code must be unique.")

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
