# License OPL-1
from odoo import _, models
from odoo.exceptions import UserError


class PurchaseOrderPaymentMixin(models.AbstractModel):
    _name = "purchase.order.payment.mixin"
    _description = "Shared logic to pay one or more purchase orders via pos.payment"

    def _get_open_pos_session(self, company):
        session = self.env["pos.session"].search(
            [("state", "=", "opened"), ("config_id.company_id", "=", company.id)],
            limit=1,
        )
        if not session:
            raise UserError(_(
                "There is no open Point of Sale session for this company. "
                "Open a session before paying a supplier this way."
            ))
        return session

    def _check_payment_method(self, payment_method, session):
        if payment_method not in session.config_id.payment_method_ids:
            raise UserError(_(
                'The payment method "%(method)s" is not configured on the '
                'open session "%(session)s".',
                method=payment_method.name,
                session=session.name,
            ))

    def _get_pos_payment_vals(self, pos_order, order, amount, payment_method, payment_date):
        """Isolated as its own method (instead of inlined in the loop below)
        so an extension module (e.g. one adding cheque fields to this
        wizard) can override it to add extra vals per payment, without
        having to reimplement the whole loop/pos.order-creation dance.
        """
        return {
            "pos_order_id": pos_order.id,
            "amount": -amount,
            "payment_method_id": payment_method.id,
            "payment_date": payment_date,
            "purchase_order_id": order.id,
        }

    def _pay_purchase_orders(self, company, partner, payment_method, payment_date, order_amounts):
        """Create one throwaway `pos.order` (the required container --
        `pos.payment.pos_order_id` is a hard `required=True` on core, see
        `pos.payment.py`) plus one negative `pos.payment` per
        `(purchase.order, amount)` pair in `order_amounts`. Each payment's
        own `create()` (overridden in `models/pos_payment.py`) immediately
        posts and reconciles the matching `account.payment` -- nothing more
        is needed here beyond creating the rows.
        """
        session = self._get_open_pos_session(company)
        self._check_payment_method(payment_method, session)
        total = sum(amount for _order, amount in order_amounts)
        pos_order = self._create_shadow_pos_order(session, company, partner, total)
        for order, amount in order_amounts:
            self.env["pos.payment"].create(
                self._get_pos_payment_vals(pos_order, order, amount, payment_method, payment_date)
            )

    def _create_shadow_pos_order(self, session, company, partner, total):
        return self.env["pos.order"].create({
            "session_id": session.id,
            "company_id": company.id,
            "partner_id": partner.id,
            "amount_total": total,
            "amount_tax": 0.0,
            "amount_paid": total,
            "amount_return": 0.0,
            "state": "paid",
        })
