from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    oph_kind = fields.Selection([
        ('consultation', "Consultation"), ('study', "Study"), ('surgery', "Surgery / procedure"),
        ('medication', "Medication / eye drops"), ('iol', "Intraocular lens"), ('contact_lens', "Contact lens"),
        ('supply', "Surgical supply"), ('optical', "Optical product"), ('other', "Other"),
    ], string="Ophthalmology Type", index=True,
        help="How the product is used in the clinic. Intraocular lenses are tracked by serial number.")
    oph_active_ingredient = fields.Char(string="Active Ingredient", translate=True,
                                        help="Generic name printed on prescriptions (Law 27.553). Example: Timolol 0.5%.")
    oph_presentation = fields.Char(string="Presentation", translate=True, help="Example: Eye drops 5 ml.")
    oph_posology = fields.Char(string="Default Posology", translate=True,
                               help="Suggested dosage when the medication is prescribed. Example: 1 drop every 12 hours.")
    oph_iol_type = fields.Selection([
        ('monofocal', "Monofocal"), ('toric', "Toric"), ('multifocal', "Multifocal"), ('edof', "Extended depth of focus"),
        ('phakic', "Phakic"), ('ac', "Anterior chamber"),
    ], string="Lens Type")
    oph_iol_constant = fields.Float(string="A Constant", digits=(4, 2),
                                    help="Manufacturer A constant used by the biometry formula. Example: 118.9.")
    oph_nomenclator_code = fields.Char(string="Nomenclator Code",
                                       help="Default code of the service in the national nomenclator.")

    @api.constrains('oph_kind', 'tracking', 'is_storable')
    def _check_oph_iol_tracking(self):
        for product in self:
            if product.oph_kind == 'iol' and product.is_storable and product.tracking == 'none':
                raise ValidationError(_("Intraocular lenses must be tracked by serial or lot number (%s).", product.name))
