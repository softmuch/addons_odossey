# License OPL-1
from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Deliberately a NEW, separate field rather than repurposing core's own
    # `state` (which the sibling `odossey_partial_payments_pos` does for
    # pos.order) -- `purchase.order.state` gates a huge amount of unrelated
    # core/`purchase_stock`/`account` behavior (receiving, invoicing
    # eligibility, list/kanban domains, etc.) that assumes `state=='purchase'`
    # means "confirmed order", not "confirmed AND unpaid". Hijacking it here
    # would risk a paid PO silently disappearing from those flows. This
    # field carries the same visual meaning (see the list view: yellow for
    # 'partially_paid', green for 'paid', mirroring pos.order's own
    # decorations) without touching what `state` itself means.
    payment_status = fields.Selection(
        [('not_paid', 'Not Paid'), ('partially_paid', 'Partially Paid'), ('paid', 'Paid')],
        compute='_compute_payment_status', store=True, string='Payment Status',
    )

    @api.depends('amount_paid', 'amount_total', 'state')
    def _compute_payment_status(self):
        for order in self:
            if order.state != 'purchase' or order.currency_id.is_zero(order.amount_paid):
                order.payment_status = 'not_paid'
            elif order.currency_id.is_zero(order.amount_total - order.amount_paid):
                order.payment_status = 'paid'
            else:
                order.payment_status = 'partially_paid'
