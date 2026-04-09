from odoo import models, fields

class PosConfig(models.Model):
    _inherit = 'pos.config'
    
    pos_receipt_before_pay = fields.Boolean(string="POS receipt Before Pay")

class ResConfigSettiongsInhert(models.TransientModel):
    _inherit = "res.config.settings"
    
    pos_receipt_before_pay = fields.Boolean(related="pos_config_id.pos_receipt_before_pay",readonly=False)
