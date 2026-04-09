from odoo import models, fields

class PosConfig(models.Model):
    _inherit = 'pos.config'
    
    odossey_pos_print_receipt = fields.Boolean(string="POS receipt Before Pay")

class ResConfigSettiongsInhert(models.TransientModel):
    _inherit = "res.config.settings"
    
    odossey_pos_print_receipt = fields.Boolean(related="pos_config_id.odossey_pos_print_receipt",readonly=False)
