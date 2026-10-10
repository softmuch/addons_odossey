from odoo import fields, models


class VetDisease(models.Model):
    _name = 'vet.disease'
    _description = 'Disease / Diagnosis'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    species_ids = fields.Many2many('vet.species', string="Species", help="Species it affects; empty = any species.")
    zoonosis = fields.Boolean(help="Transmissible to humans: the owner must be informed of the precautions.")
    notifiable = fields.Boolean(string="Notifiable",
                                help="Disease of mandatory notification to the health authority (SENASA / zoonosis service).")
    vaccine_preventable = fields.Boolean(string="Vaccine Preventable")
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
