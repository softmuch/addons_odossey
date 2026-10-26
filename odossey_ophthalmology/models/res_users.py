from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    oph_is_ophthalmologist = fields.Boolean(
        string="Ophthalmologist",
        help="Can be selected as the professional of exams, prescriptions, surgeries and certificates.")
    oph_is_technician = fields.Boolean(
        string="Technician / Orthoptist",
        help="Performs the pre-consultation (visual acuity, refraction, pressure) and the complementary studies.")
    oph_license = fields.Char(string="National License (MN)",
                              help="National professional license number (matrícula nacional), printed on "
                                   "prescriptions, certificates and reports.")
    oph_license_provincial = fields.Char(string="Provincial License (MP)",
                                         help="Provincial license number (matrícula provincial), when applicable.")
    oph_specialty = fields.Char(string="Specialty", default="Oftalmología",
                                help="Specialty printed under the name. Example: Oftalmología - Retina y vítreo.")
    oph_signature = fields.Image(string="Signature & Stamp", max_width=600, max_height=300,
                                 help="Scanned signature and stamp, printed on prescriptions, certificates and reports.")
    oph_color = fields.Integer(string="Agenda Color")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['oph_is_ophthalmologist', 'oph_is_technician', 'oph_license',
                                               'oph_license_provincial', 'oph_specialty', 'oph_signature']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['oph_license', 'oph_license_provincial', 'oph_specialty', 'oph_signature']
