# License OPL-1
from odoo import _, api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    pos_payment_ids = fields.One2many(
        comodel_name="pos.payment",
        inverse_name="purchase_order_id",
        string="Payments",
    )
    # `store=True`: a "Group By Proveedor" list groups via a server-side
    # `read_group` SQL aggregation, which can only sum a real DB column --
    # an unstored compute field's `sum=` attribute silently stops showing
    # any total (per-group or grand total) the moment the list is grouped,
    # even though it still summed fine client-side in the ungrouped view.
    amount_paid = fields.Monetary(compute="_compute_amount_paid", string="Paid", store=True)
    amount_difference = fields.Monetary(
        compute="_compute_amount_paid", string="Due", store=True
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
