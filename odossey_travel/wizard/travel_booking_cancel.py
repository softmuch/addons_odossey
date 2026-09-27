from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_amount


class TravelBookingCancel(models.TransientModel):
    _name = 'travel.booking.cancel'
    _description = "Cancel Travel Booking"

    sale_order_id = fields.Many2one('sale.order', string="Booking", required=True, readonly=True)
    trip_id = fields.Many2one(related='sale_order_id.trip_id')
    currency_id = fields.Many2one(related='sale_order_id.currency_id')
    cancel_date = fields.Date(string="Cancellation Date", required=True,
                              default=fields.Date.context_today)
    days_before = fields.Integer(string="Days Before Departure", compute='_compute_days_before')
    policy_id = fields.Many2one('travel.cancellation.policy', string="Policy",
                                compute='_compute_policy', store=True, readonly=False)
    penalty_percent = fields.Float(string="Penalty (%)", compute='_compute_penalty_percent',
                                   store=True, readonly=False)
    amount_total = fields.Monetary(related='sale_order_id.amount_total', string="Booking Total")
    amount_paid = fields.Monetary(related='sale_order_id.travel_amount_paid', string="Paid")
    deposit_paid = fields.Monetary(string="Deposit Paid", compute='_compute_amounts')
    penalty_amount = fields.Monetary(string="Penalty Retained", compute='_compute_penalty_amount',
                                     store=True, readonly=False)
    refund_amount = fields.Monetary(string="Amount to Refund", compute='_compute_amounts')
    amount_owed = fields.Monetary(
        string="Amount Owed by Customer", compute='_compute_amounts',
        help="Part of the penalty not covered by the payments already received.")
    reason = fields.Char(string="Reason", required=True)

    @api.depends('cancel_date', 'trip_id.date_start')
    def _compute_days_before(self):
        for wizard in self:
            wizard.days_before = ((wizard.trip_id.date_start - wizard.cancel_date).days
                                  if wizard.trip_id.date_start and wizard.cancel_date else 0)

    @api.depends('trip_id')
    def _compute_policy(self):
        for wizard in self:
            wizard.policy_id = wizard.trip_id.cancellation_policy_id

    @api.depends('policy_id', 'days_before')
    def _compute_penalty_percent(self):
        for wizard in self:
            wizard.penalty_percent = (wizard.policy_id._get_penalty_percent(wizard.days_before)
                                      if wizard.policy_id else 0.0)

    @api.depends('penalty_percent', 'amount_total', 'amount_paid', 'policy_id')
    def _compute_penalty_amount(self):
        for wizard in self:
            order = wizard.sale_order_id
            deposit_paid = min(order.travel_amount_paid, order.travel_deposit_required)
            penalty = wizard.amount_total * wizard.penalty_percent / 100.0
            if not wizard.policy_id.deposit_refundable:
                penalty = max(penalty, deposit_paid)
            wizard.penalty_amount = wizard.currency_id.round(penalty)

    @api.depends('penalty_amount', 'amount_paid')
    def _compute_amounts(self):
        for wizard in self:
            order = wizard.sale_order_id
            paid = order.travel_amount_paid
            wizard.deposit_paid = min(paid, order.travel_deposit_required)
            wizard.refund_amount = max(paid - wizard.penalty_amount, 0.0)
            wizard.amount_owed = max(wizard.penalty_amount - paid, 0.0)

    def action_confirm(self):
        self.ensure_one()
        order = self.sale_order_id
        if order.state == 'cancel':
            raise UserError(self.env._("The booking is already cancelled."))
        paid = order.travel_amount_paid
        refund = max(paid - self.penalty_amount, 0.0)
        order.write({
            'travel_cancel_date': self.cancel_date,
            'travel_cancel_reason': self.reason,
            'travel_penalty_amount': self.penalty_amount,
            'travel_refund_amount': refund,
        })
        order.with_context(disable_cancel_warning=True)._action_cancel()

        def fmt(amount):
            return format_amount(self.env, amount, order.currency_id)

        order.message_post(body=Markup(
            "<p><b>%s</b></p><ul><li>%s: %s</li><li>%s: %s</li><li>%s: %s (%s%%)</li>"
            "<li>%s: %s</li></ul>") % (
            self.env._("Booking cancelled"),
            self.env._("Reason"), self.reason,
            self.env._("Paid"), fmt(paid),
            self.env._("Penalty retained"), fmt(self.penalty_amount), self.penalty_percent,
            self.env._("Amount to refund"), fmt(refund),
        ))
        if refund and not order.currency_id.is_zero(refund):
            order.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=self.env._("Refund %s to the customer", fmt(refund)),
                note=self.env._("Issue the credit note and the refund of the cancelled booking."),
                user_id=(order.trip_id.user_id or self.env.user).id,
            )
        return {'type': 'ir.actions.act_window_close'}
