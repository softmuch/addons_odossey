# License OPL-1
from odoo import api, fields, models


class L10nLatamCheck(models.Model):
    _inherit = "l10n_latam.check"

    # Core declares this `related='payment_id.currency_id'` with no
    # `store=True`/`readonly=False` -- same problem `l10n_latam_check_ext`
    # already fixed for `company_id`/`partner_id` (a check created there has
    # no `payment_id` yet, so any plain related off it resolves empty
    # forever). Needed here so a check handed over to a supplier still has
    # a real currency to compare against the outbound payment's.
    currency_id = fields.Many2one(related="payment_id.currency_id", store=True, readonly=False)

    handed_to_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Girado a",
        readonly=True,
        copy=False,
        help="Set when this third-party check was handed over to a "
        "supplier to settle a purchase order, instead of being deposited "
        "or going through core's own third-party-check-transfer flow "
        "(which requires the check to have first been received through a "
        "real journal -- not the case for a check tracked via "
        "l10n_latam_check_ext's instant, journal-less creation).",
    )
    handed_date = fields.Date(string="Fecha de giro", readonly=True, copy=False)

    # Purchase orders this check paid (fully or partially). Every purchase
    # payment settled with a check -- a brand new own check, or a customer's
    # check handed over ("girado") -- is one `pos.payment` per order linked
    # to the check, so the whole picture is derivable from those rows.
    purchase_payment_ids = fields.One2many(
        comodel_name="pos.payment",
        inverse_name="l10n_latam_check_id",
        domain=[("purchase_order_id", "!=", False)],
        string="Pagos de compra",
        readonly=True,
    )
    purchase_order_ids = fields.Many2many(
        comodel_name="purchase.order",
        string="Órdenes de compra pagadas",
        compute="_compute_purchase_payment_info",
    )
    purchase_paid_amount = fields.Monetary(
        string="Aplicado a órdenes",
        compute="_compute_purchase_payment_info",
        help="Part of the check's amount that went to purchase orders.",
    )
    purchase_surplus_amount = fields.Monetary(
        string="Excedente",
        compute="_compute_purchase_payment_info",
        help="Part of the check's amount NOT applied to any order (e.g. "
        "banked as supplier credit).",
    )

    @api.depends("purchase_payment_ids.amount", "amount")
    def _compute_purchase_payment_info(self):
        for check in self:
            payments = check.purchase_payment_ids
            check.purchase_order_ids = payments.purchase_order_id
            check.purchase_paid_amount = sum(abs(p.amount) for p in payments)
            check.purchase_surplus_amount = (
                max(check.amount - check.purchase_paid_amount, 0.0) if payments else 0.0
            )

    def action_edit_own_check(self):
        return self._action_open_form_view(
            "odossey_purchase_pos_payment_check.l10n_latam_check_view_form_handed_edit"
        )

    def action_lock_own_check(self):
        return self._action_open_form_view(
            "odossey_purchase_pos_payment_check.l10n_latam_check_view_form_handed"
        )
