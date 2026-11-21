from odoo import models, fields


class PosOrder(models.Model):
    _inherit = 'pos.order'

    is_delivery = fields.Boolean(string='Is Delivery', default=False)

    def _process_saved_order(self, draft):
        res = super()._process_saved_order(draft)
        # The payment state of the delivery record is set here, server side, in the
        # same transaction that saves the paid order. Doing it from the PaymentScreen
        # was unreliable: the screen is destroyed right after validation and its
        # protected ORM calls never completed (record stayed "unpaid").
        if self.is_delivery and self.state in ('paid', 'done', 'invoiced'):
            self.env['pos.delivery.order'].sudo()._mark_paid_from_pos_orders(self, notify=True)
        return res
