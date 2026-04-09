from odoo import models, api

class PosSession(models.Model):
    _inherit = "pos.session"

    @api.model
    def _load_pos_data_models(self, config_id):
        models = super()._load_pos_data_models(config_id)
        return models + ["ab_pos.order.change", "ab_pos.order.change.line"]


    def load_data(self, models_to_load, only_data=False, abichinger_kitchen_screen=False):
        self_ctx = self.with_context(abichinger_kitchen_screen=abichinger_kitchen_screen)
        response: dict = super(PosSession, self_ctx).load_data(models_to_load, only_data=only_data)
        return response