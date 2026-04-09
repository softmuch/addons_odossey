from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    """
    NOTES
    1. Fields with name starting with 'pos_' are removed from the vals before super call to `create`.
       Values of these fields are written to `pos_config_id` record after the super call.
       This is done so that these fields are written at the same time to the active pos.config record.
    """
    _inherit = 'res.config.settings'

    pos_kitchen_ids = fields.Many2many(related='pos_config_id.kitchen_ids', readonly=False)
