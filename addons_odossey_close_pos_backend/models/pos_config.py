from odoo import models, _
from odoo.exceptions import UserError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def action_close_session_from_kanban(self):
        """Open the real POS session UI and trigger its closing popup.

        Reuses the exact front-end closing flow (cash count, payment
        breakdown, difference validation, wizard on imbalance...) instead of
        reimplementing it in the backend: navigates into /pos/ui like
        open_ui does, with an extra `close_session` flag picked up by our JS
        override (static/src/overrides/pos_store.js) to call
        PosStore.closeSession() as soon as the session data is loaded.
        """
        self.ensure_one()
        if not self.current_session_id:
            raise UserError(_("There is no open session to close."))
        pos_url = '/pos/ui/%d?from_backend=True&close_session=True' % self.id
        return {
            'type': 'ir.actions.act_url',
            'url': pos_url,
            'target': 'self',
        }
