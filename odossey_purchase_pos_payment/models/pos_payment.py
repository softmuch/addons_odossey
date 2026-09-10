# License OPL-1
from odoo import api, fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    purchase_order_id = fields.Many2one(
        comodel_name="purchase.order",
        string="Purchase Order",
        index=True,
        help="Set when this payment represents money paid OUT to a "
        "supplier against this purchase order (amount is negative in that "
        "case) rather than money collected from a POS sale.",
    )
    # `pos_order_id` is deliberately left empty for a supplier payment (see
    # `_pay_purchase_orders` in the wizard mixin -- there's no real POS sale
    # to attach it to, so no shadow `pos.order` is created just to satisfy
    # the field). Core declares it `required=True`; relaxed here since a
    # purchase payment genuinely has none.
    pos_order_id = fields.Many2one(required=False)
    # `company_id`/`partner_id`/`currency_id` are core `related` fields
    # sourced FROM `pos_order_id`, so they'd otherwise come out empty here
    # too. Redeclared `store=True, readonly=False` (same fix already applied
    # to `l10n_latam.check.company_id`/`partner_id` in `l10n_latam_check_ext`
    # for the identical reason: an Odoo related field without
    # `readonly=False` silently ignores any value passed to it in
    # `create()`/`write()` and always recomputes from the relation instead)
    # so `_get_pos_payment_vals` below can set them explicitly from the
    # purchase order. `session_id`/`user_id` are left as plain empty
    # `related` fields -- nothing in this module's own code needs them, and
    # they're excluded from `rule_pos_payment_multi_company`/the payment-
    # method-vs-session constrain that would otherwise choke on them (see
    # `_check_payment_method_id` below).
    company_id = fields.Many2one(related="pos_order_id.company_id", store=True, readonly=False)
    partner_id = fields.Many2one(related="pos_order_id.partner_id", store=True, readonly=False)
    currency_id = fields.Many2one(related="pos_order_id.currency_id", store=True, readonly=False)

    @api.constrains("payment_method_id")
    def _check_payment_method_id(self):
        """Core's own version validates `payment_method_id` against the
        payment's `session_id.config_id.payment_method_ids` -- meaningless
        for a supplier payment, which never has a `pos_order_id`/session at
        all (see the field comments above): without this override, core's
        constrain would reject EVERY one of these on create, since an empty
        `session_id.config_id.payment_method_ids` never contains anything.
        Only run core's check on payments that actually belong to a real
        POS sale.
        """
        return super(PosPayment, self.filtered("pos_order_id"))._check_payment_method_id()

    def create(self, vals_list):
        payments = super().create(vals_list)
        # A caller that needs a SINGLE `account.payment` shared across
        # several of these payments at once (e.g. handing over one existing
        # third-party check -- one fixed physical amount -- to settle
        # several purchase orders in one go, see
        # `odossey_purchase_pos_payment_check`) sets this context key to
        # build that shared `account.payment` itself instead.
        if not self.env.context.get("skip_purchase_order_account_payment"):
            payments.filtered("purchase_order_id")._create_purchase_order_account_payment()
        return payments

    def _create_purchase_order_account_payment(self):
        """Post and reconcile a real, outbound, supplier `account.payment`
        for each payment in `self` that has `purchase_order_id` set.

        `pos.payment` itself never triggers any accounting on its own
        outside of a POS session close (see `pos.session._accumulate_amounts`
        / `_create_combine_account_payment`, which only ever walk
        `session.order_ids.payment_ids` -- a payment's own `session_id` is
        just a denormalized convenience field, never the real join key for
        money totals) or an instant customer invoice
        (`pos.payment._create_payment_moves`, hardwired to the RECEIVABLE
        account). Neither applies to a supplier payment, so this is done
        here explicitly, immediately, using the same standard
        `account.payment.register` wizard used everywhere else in Odoo to
        register a payment against one or more open bills -- reused instead
        of hand-building the `account.payment` + reconciliation (like
        `l10n_latam_check_ext`'s `_create_invoiced_check_account_payment`
        does for POS cheques) because that hand-rolled pattern exists there
        only to wire in POS-specific `outstanding_account_id` bookkeeping;
        nothing here needs that, and the wizard already handles multi-bill
        allocation and partial reconciliation correctly on its own.
        """
        for payment in self:
            purchase_order = payment.purchase_order_id
            journal = payment.payment_method_id.journal_id
            open_bills = purchase_order._get_open_bills()
            if open_bills:
                register = (
                    self.env["account.payment.register"]
                    .with_context(active_model="account.move", active_ids=open_bills.ids)
                    .create(
                        {
                            "payment_date": payment.payment_date,
                            "amount": abs(payment.amount),
                            "journal_id": journal.id,
                            "group_payment": True,
                        }
                    )
                )
                account_payments = register._create_payments()
            else:
                # No open bill yet to reconcile against (e.g. paying an
                # advance before the vendor bill exists) -- still record a
                # real outbound payment, left unreconciled until a future
                # bill nets against it, same as core's own "Register
                # Payment without an invoice" flow.
                #
                # `write_off_line_vals: []` looks like a no-op (an empty
                # write-off) but isn't: without this key at all, a freshly
                # created `account.payment` stays `state='draft'` until
                # `action_post()` is called on it separately -- and on a
                # journal whose only outbound payment method line is a
                # l10n_latam_check-coded one (e.g. "out_third_party_checks",
                # common for a "Cheque" pos.payment.method's journal),
                # `action_post()` on a still-`draft` record triggers
                # `l10n_latam_check`'s own validation requiring
                # `l10n_latam_move_check_ids`/`l10n_latam_new_check_ids` to
                # match the amount -- which nothing here ever sets, since
                # this module deliberately does not use that OCA check-move
                # mechanism (see `odossey_purchase_pos_payment_check`).
                # `account.payment.register._create_payments()` never hits
                # this at all because it always passes `write_off_line_vals`
                # (even as `[]`) in its own create vals, which makes the
                # payment's `state` resolve directly to `in_process`
                # (skipping `draft` entirely) -- confirmed empirically by
                # bisecting its exact create vals field-by-field. Passing it
                # here too reproduces that same effect for a bill-less
                # advance payment.
                account_payments = self.env["account.payment"].create(
                    {
                        "payment_type": "outbound",
                        "partner_type": "supplier",
                        "partner_id": purchase_order.partner_id.id,
                        "amount": abs(payment.amount),
                        "journal_id": journal.id,
                        "date": payment.payment_date,
                        "memo": purchase_order.name,
                        "write_off_line_vals": [],
                    }
                )
                account_payments.action_post()
            payment.account_move_id = account_payments.move_id[:1].id
