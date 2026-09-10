# License OPL-1
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrderPaymentMixin(models.AbstractModel):
    _inherit = "purchase.order.payment.mixin"

    # `payment_method_type` (needed for the same reason as
    # `pos.payment.payment_method_type` in l10n_latam_check_ext -- see
    # `wizard/purchase_order_payment.py`) is declared separately on each
    # concrete wizard, NOT here: a `related` field's target path is
    # validated against this model's own fields at definition time, and
    # `payment_method_id` only exists on the concrete wizards.
    check_mode = fields.Selection(
        selection=[("new", "New Check"), ("existing", "Existing Check")],
        default="new",
        string="Check",
    )
    existing_check_id = fields.Many2one(
        comodel_name="l10n_latam.check",
        string="Check to Hand Over",
        domain="[('company_id', '=', company_id), ('handed_to_partner_id', '=', False)]",
        help="An existing third-party check already in the company's "
        "portfolio (received from a customer) -- handing it over to a "
        "supplier instead of creating a brand new check record.",
    )
    l10n_latam_check_number = fields.Char(string="Check Number")
    l10n_latam_check_bank_id = fields.Many2one(comodel_name="res.bank", string="Issuing Bank")
    l10n_latam_check_issuer_vat = fields.Char(string="Issuer VAT")
    l10n_latam_check_type = fields.Selection(
        selection=[
            ("common", "Common Check"),
            ("deferred", "Deferred Payment Check (CPD)"),
        ],
        string="Check Type",
    )
    l10n_latam_check_issue_date = fields.Date(string="Issue Date")
    l10n_latam_check_payment_date = fields.Date(string="Payment Date")

    @api.onchange("existing_check_id")
    def _onchange_existing_check_id(self):
        if self.existing_check_id:
            self.amount = self.existing_check_id.amount

    def _is_free_amount_entry(self):
        if self.check_mode == "existing" and self.existing_check_id:
            return False
        return super()._is_free_amount_entry()

    def _pay_purchase_orders(self, company, partner, payment_method, payment_date, order_amounts):
        if payment_method.payment_method_type != "check":
            return super()._pay_purchase_orders(
                company, partner, payment_method, payment_date, order_amounts
            )
        if self.check_mode == "existing":
            if not self.existing_check_id:
                raise UserError(_("Select an existing check to hand over."))
            return self._pay_with_existing_check(
                company, partner, payment_method, payment_date, order_amounts
            )

        # 'new' check mode: same duplicate-check problem/fix as before -- one
        # `l10n_latam.check` created up front for the total, threaded via
        # context into every payment's vals (an Odoo recordset doesn't allow
        # ad-hoc instance attributes) so `pos.payment`'s own
        # `_l10n_latam_ensure_check()` (l10n_latam_check_ext) doesn't create
        # a separate check per payment.
        self.env["pos.payment"]._l10n_latam_check_require_real_partner(partner)
        total = sum(amount for _order, amount in order_amounts)
        check = self.env["l10n_latam.check"].sudo().create({
            "name": self.l10n_latam_check_number,
            "bank_id": self.l10n_latam_check_bank_id.id,
            "issuer_vat": self.l10n_latam_check_issuer_vat,
            "check_type": self.l10n_latam_check_type,
            "issue_date": self.l10n_latam_check_issue_date,
            "payment_date": self.l10n_latam_check_payment_date or payment_date,
            "amount": total,
            "company_id": company.id,
            "partner_id": partner.id,
        })
        return super(
            PurchaseOrderPaymentMixin, self.with_context(_l10n_latam_check_id=check.id)
        )._pay_purchase_orders(company, partner, payment_method, payment_date, order_amounts)

    def _get_pos_payment_vals(self, order, amount, payment_method, payment_date):
        # Threads the check created up front in the 'new check' branch above
        # into every payment's own vals (see the comment there for why this
        # goes through context instead of an instance attribute). Only
        # applies to that branch: `_pay_with_existing_check` builds its own
        # `pos.payment` vals directly and never reaches this method.
        vals = super()._get_pos_payment_vals(order, amount, payment_method, payment_date)
        if payment_method.payment_method_type == "check":
            vals["l10n_latam_check_id"] = self.env.context.get("_l10n_latam_check_id")
            vals["l10n_latam_check_number"] = self.l10n_latam_check_number
        return vals

    def _pay_with_existing_check(self, company, partner, payment_method, payment_date, order_amounts):
        """A real, physical check has one fixed face value and can only be
        handed over once, in full, to one recipient -- so this creates
        exactly ONE `account.payment` for the check's own full amount
        (never a fraction). One `pos.payment` per order is still created
        (for that order's own "Payments" tab), all sharing this same check,
        but none of them trigger their own separate `account.payment` (see
        `skip_purchase_order_account_payment` in
        `odossey_purchase_pos_payment/models/pos_payment.py`).

        Deliberately does NOT use core `l10n_latam_check`'s own
        "move a third-party check" mechanism (`l10n_latam_move_check_ids` /
        the journal's `out_third_party_checks` payment method line): that
        mechanism requires the check to already have a `current_journal_id`
        (set only once a check has gone through a real inbound
        `account.payment`), which a check tracked via
        `l10n_latam_check_ext`'s instant, journal-less creation never has --
        it would always be rejected ("some checks are not anymore in
        journal"). Instead this reuses the exact same
        `account.payment.register`-based path already used for the 'new
        check' case above (proven to work against this same journal), and
        marks the check as handed over via `handed_to_partner_id` purely
        for our own tracking/reporting (see "Cheques Propios" in
        `views/purchase_check_views.xml`) -- not core's own check ledger.
        """
        check = self.existing_check_id

        payments = self.env["pos.payment"]
        for order, amount in order_amounts:
            payments |= self.env["pos.payment"].with_context(
                skip_purchase_order_account_payment=True
            ).create({
                "company_id": order.company_id.id,
                "partner_id": order.partner_id.id,
                "currency_id": order.currency_id.id,
                "amount": -amount,
                "payment_method_id": payment_method.id,
                "payment_date": payment_date,
                "purchase_order_id": order.id,
                "l10n_latam_check_id": check.id,
            })

        journal = payment_method.journal_id
        open_bills = self.env["account.move"]
        for order, _amount in order_amounts:
            open_bills |= order._get_open_bills()
        if open_bills:
            register = self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=open_bills.ids,
            ).create({
                "payment_date": payment_date,
                "amount": check.amount,
                "journal_id": journal.id,
                "group_payment": True,
            })
            account_payments = register._create_payments()
        else:
            # See the matching comment in
            # `odossey_purchase_pos_payment/models/pos_payment.py` --
            # `write_off_line_vals: []` is what makes this payment's `state`
            # resolve straight to `in_process` (skipping `draft`), which is
            # what lets it dodge `l10n_latam_check`'s
            # `l10n_latam_move_check_ids` validation on this check-coded
            # journal despite that field being intentionally left empty.
            account_payments = self.env["account.payment"].create({
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": partner.id,
                "amount": check.amount,
                "journal_id": journal.id,
                "date": payment_date,
                "memo": ", ".join(order.name for order, _amount in order_amounts),
                "write_off_line_vals": [],
            })
            account_payments.action_post()
        payments.account_move_id = account_payments.move_id[:1].id

        check.write({"handed_to_partner_id": partner.id, "handed_date": payment_date})
