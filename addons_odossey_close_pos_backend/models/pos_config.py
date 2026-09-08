from odoo import models, _
from odoo.exceptions import UserError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def action_close_session_from_kanban(self):
        """Open a backend wizard to close the currently open session.

        Stays entirely in the backend (no navigation into /pos/ui): the
        wizard (pos.close.session.backend.wizard) calls the same session
        methods the POS front-end uses to close a register
        (post_closing_cash_details, update_closing_control_state_session,
        action_pos_session_closing_control), including the hand-off to the
        core pos.close.session.wizard when there's an accounting imbalance.
        """
        self.ensure_one()
        if not self.current_session_id:
            raise UserError(_("There is no open session to close."))
        return {
            'name': _('Cerrar caja registradora'),
            'type': 'ir.actions.act_window',
            'res_model': 'pos.close.session.backend.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_session_id': self.current_session_id.id},
        }
