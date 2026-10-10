from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    vet_is_veterinarian = fields.Boolean(string="Veterinarian",
                                         help="Can be selected as the professional of consultations, prescriptions and certificates.")
    vet_license = fields.Char(string="Professional License No.",
                              help="Professional license number (Argentina: matrícula provincial; Italy: iscrizione all'Ordine), "
                                   "printed on prescriptions and certificates.")
    vet_college = fields.Char(string="Professional Body",
                              help="College / council that issued the license, e.g. Colegio de Veterinarios de la Provincia de Buenos Aires.")
    vet_signature = fields.Image(string="Signature & Stamp", max_width=600, max_height=300,
                                 help="Scanned signature and stamp, printed on prescriptions and certificates.")
    vet_color = fields.Integer(string="Agenda Color")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['vet_is_veterinarian', 'vet_license', 'vet_college', 'vet_signature']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['vet_license', 'vet_college', 'vet_signature']
