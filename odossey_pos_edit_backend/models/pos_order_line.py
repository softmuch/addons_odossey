# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import UserError


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_order_state(self):
        # A backend-reopened order (action_rioseed_reopen_draft) is already
        # 'draft' by the time its lines become editable in the UI (the
        # form's `lines` field is readonly="state != 'draft'"), so core's own
        # draft/cancel-only guard already covers the intended edit flow --
        # this override only adds the account_move/nb_print check on top of
        # core's states. Deliberately NOT extending the allowed states to
        # ('paid', 'done') like an earlier version of this override did:
        # that let a line be unlinked straight off a paid/done order without
        # ever going through action_rioseed_reopen_draft, silently skipping
        # the whole snapshot/correction-picking pipeline in
        # action_rioseed_confirm_edit.
        if self.filtered(lambda l: (
            l.order_id.state not in ('draft', 'cancel')
            or l.order_id.account_move
            or l.order_id.nb_print > 0
        )):
            raise UserError(_(
                "You can only unlink PoS order lines that are related to orders in "
                "new or cancelled state (not invoiced, not printed)."
            ))
