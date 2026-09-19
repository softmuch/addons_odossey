# License OPL-1
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrderPayFreely(models.TransientModel):
    _name = "purchase.order.pay.freely"
    _inherit = "purchase.order.payment.mixin"
    _description = "Pay Freely a Supplier's Open Purchase Orders"

    company_id = fields.Many2one(
        comodel_name="res.company", default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        required=True,
        domain="[('supplier_rank', '>', 0)]",
    )
    payment_method_id = fields.Many2one(
        comodel_name="pos.payment.method",
        required=True,
        domain="[('company_id', '=', company_id), ('show_in_purchase', '=', True)]",
    )
    # Expressed in the company currency. Open orders in any OTHER currency
    # are converted with the rates in `rate_ids` (one line per foreign
    # currency found among the supplier's open orders).
    amount = fields.Monetary(required=True)
    payment_date = fields.Date(default=fields.Date.context_today, required=True)
    rate_ids = fields.One2many(
        comodel_name="purchase.order.pay.freely.rate",
        inverse_name="wizard_id",
        string="Exchange Rates",
    )

    def _get_open_orders(self):
        self.ensure_one()
        orders = self.env["purchase.order"].search([
            ("partner_id", "=", self.partner_id.id),
            ("company_id", "=", self.company_id.id),
            ("state", "=", "purchase"),
        ])
        return orders.filtered(lambda o: o.amount_difference > 0).sorted("date_order")

    def _get_rate(self, currency):
        """The rate typed in the wizard, or the current one from the
        currency table if the line isn't there (yet)."""
        self.ensure_one()
        line = self.rate_ids.filtered(lambda r: r.currency_id == currency)[:1]
        if line and line.rate > 0:
            return line.rate
        return super()._get_rate(currency)

    def _get_total_residual(self):
        self.ensure_one()
        return sum(self._get_order_residual(o) for o in self._get_open_orders())

    def _fill_rates(self):
        """One rate line per foreign currency among the open orders,
        defaulted to the current rate of the currency table."""
        self.ensure_one()
        company_currency = self.company_id.currency_id
        commands = [Command.clear()]
        if self.partner_id:
            for currency in self._get_open_orders().currency_id - company_currency:
                commands.append(Command.create({
                    "currency_id": currency.id,
                    "rate": super()._get_rate(currency),
                }))
        self.rate_ids = commands

    def _get_default_amount(self):
        """Amount suggested once the partner/rates are known."""
        self.ensure_one()
        return self._get_total_residual()

    @api.onchange("partner_id")
    def _onchange_partner_id_amount(self):
        if self.partner_id:
            self._fill_rates()
            self.amount = self._get_default_amount()

    @api.onchange("rate_ids")
    def _onchange_rate_ids(self):
        if self.partner_id:
            self.amount = self._get_default_amount()

    def _distribute_amount(self, orders, amount):
        """Spread `amount` (company currency) over `orders`, oldest first.
        Returns `([(order, applied)], leftover)`, all in company currency."""
        self.ensure_one()
        currency = self.company_id.currency_id
        remaining = amount
        order_amounts = []
        for order in orders:
            if remaining <= 0:
                break
            applied = min(remaining, self._get_order_residual(order))
            if applied <= 0:
                continue
            order_amounts.append((order, applied))
            remaining = currency.round(remaining - applied)
        return order_amounts, remaining

    @api.onchange("amount")
    def _onchange_amount_cap(self):
        if self.partner_id and self._is_free_amount_entry():
            total_residual = self._get_total_residual()
            if self.amount > total_residual:
                self.amount = total_residual

    def _is_free_amount_entry(self):
        """True when `amount` is a number the user typed in and should be
        capped/validated against the total open balance. False when it's
        instead driven by a fixed real-world instrument (e.g. handing over
        an existing check for its own face value in
        `odossey_purchase_pos_payment_check`) -- overpaying relative to
        currently-open orders is then a normal, valid outcome (the
        supplier ends up with a credit balance), not a mistake to block.
        """
        return True

    def action_pay(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_("The amount to pay must be greater than zero."))
        orders = self._get_open_orders()
        total_residual = self._get_total_residual()
        if self._is_free_amount_entry() and self.amount > total_residual:
            raise UserError(_(
                "The amount exceeds this supplier's total open balance "
                "(%(total)s).", total=total_residual,
            ))

        order_amounts, _remaining = self._distribute_amount(orders, self.amount)

        self._pay_purchase_orders(
            self.company_id, self.partner_id, self.payment_method_id,
            self.payment_date, order_amounts,
        )
        return True
