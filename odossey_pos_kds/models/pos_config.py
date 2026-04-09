from odoo import fields, models

class PosConfig(models.Model):
    _inherit = 'pos.config'

    kitchen_ids = fields.Many2many("ab_pos.kitchen_screen", "ab_pos_kitchen_screen_pos_config_rel", "config_id", "kitchen_id", string="Kitchen Screen")

    def open_kitchen(self, params: dict = {}):
        self.ensure_one()
        if not self.kitchen_ids:
            return

        return self.kitchen_ids[0].open_kitchen()
    
    def _get_all_kitchen_ids(self):
        self.ensure_one()
        return self.env['ab_pos.kitchen_screen'].search(['|', ("id", "in", self.kitchen_ids.ids), ("config_ids", "=", False)])
    

    
