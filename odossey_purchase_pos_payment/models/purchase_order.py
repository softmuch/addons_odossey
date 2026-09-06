# License OPL-1
from odoo import _, api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    pos_payment_ids = fields.One2many(
        comodel_name="pos.payment",
        inverse_name="purchase_order_id",
        string="Payments",
    )
    amount_paid = fields.Monetary(compute="_compute_amount_paid", string="Paid")
    amount_difference = fields.Monetary(
        compute="_compute_amount_paid", string="Due"
    )

    @api.depends("pos_payment_ids.amount", "amount_total")
    def _compute_amount_paid(self):
        for order in self:
            order.amount_paid = sum(
                abs(payment.amount) for payment in order.pos_payment_ids
            )
            order.amount_difference = order.amount_total - order.amount_paid

    def _get_open_bills(self):
        self.ensure_one()
        return self.invoice_ids.filtered(
            lambda move: move.state == "posted"
            and move.payment_state not in ("paid", "reversed", "in_payment")
        )

    def action_purchase_pay(self):
        self.ensure_one()
        return {
            "name": _("Pay"),
            "type": "ir.actions.act_window",
            "res_model": "purchase.order.payment",
            "view_mode": "form",
            "target": "new",
            "context": {"default_purchase_order_id": self.id},
        }
