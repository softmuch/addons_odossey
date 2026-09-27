from odoo import fields, models, tools

from ..models.travel_passenger import BOOKING_STATES


class TravelForecastReport(models.Model):
    """Revenue forecast per booking, weighted by the probability of cancellation.

    expected revenue = total x (1 - p) + retained deposit x p
    where p depends on the booking status (configurable in the settings) and the retained
    deposit is the part of the deposit already paid (non refundable). Cancelled bookings
    contribute with the penalty actually retained. Quotations are weighted by the quotation
    win rate. Amounts are in the company currency.
    """
    _name = 'travel.forecast.report'
    _description = "Travel Revenue Forecast"
    _auto = False
    _order = 'date_departure, trip_id'

    order_id = fields.Many2one('sale.order', string="Booking", readonly=True)
    trip_id = fields.Many2one('travel.trip', string="Trip", readonly=True)
    trip_state = fields.Selection(related='trip_id.state', string="Trip Status")
    partner_id = fields.Many2one('res.partner', string="Customer", readonly=True)
    travel_group_id = fields.Many2one('travel.group', string="Group", readonly=True)
    user_id = fields.Many2one('res.users', string="Salesperson", readonly=True)
    company_id = fields.Many2one('res.company', string="Company", readonly=True)
    currency_id = fields.Many2one('res.currency', string="Currency", readonly=True)
    date_departure = fields.Date(string="Departure", readonly=True)
    booking_state = fields.Selection(BOOKING_STATES, string="Booking Status", readonly=True)
    pax_count = fields.Integer(string="Passengers", readonly=True)
    amount_total = fields.Monetary(string="Total", readonly=True)
    amount_untaxed = fields.Monetary(string="Untaxed Total", readonly=True)
    amount_paid = fields.Monetary(string="Collected", readonly=True)
    amount_due = fields.Monetary(string="Pending Balance", readonly=True)
    deposit_required = fields.Monetary(string="Deposit", readonly=True)
    cancel_probability = fields.Float(string="Cancellation Probability (%)", readonly=True,
                                      aggregator='avg')
    expected_revenue = fields.Monetary(string="Expected Revenue", readonly=True)
    expected_net_revenue = fields.Monetary(string="Expected Net Revenue", readonly=True,
                                           help="Expected revenue without taxes.")
    expected_cost = fields.Monetary(string="Expected Supplier Cost", readonly=True)
    expected_margin = fields.Monetary(string="Expected Margin", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    b.*,
                    b.expected_net_revenue - b.expected_cost AS expected_margin
                FROM (
                    SELECT
                        so.id AS id,
                        so.id AS order_id,
                        so.trip_id,
                        so.partner_id,
                        so.travel_group_id,
                        so.user_id,
                        so.company_id,
                        c.currency_id,
                        t.date_start AS date_departure,
                        so.travel_booking_state AS booking_state,
                        so.travel_pax_count AS pax_count,
                        so.amount_total / cr.rate AS amount_total,
                        so.amount_untaxed / cr.rate AS amount_untaxed,
                        so.travel_amount_paid / cr.rate AS amount_paid,
                        so.travel_amount_due / cr.rate AS amount_due,
                        so.travel_deposit_required / cr.rate AS deposit_required,
                        pr.p AS cancel_probability,
                        rev.expected AS expected_revenue,
                        rev.expected * CASE WHEN so.amount_total <> 0
                            THEN so.amount_untaxed / so.amount_total ELSE 1 END
                            AS expected_net_revenue,
                        CASE WHEN so.travel_booking_state = 'cancelled' THEN 0
                            ELSE COALESCE(t.cost_per_person, 0) * so.travel_pax_count
                                 / cr.rate * (1 - pr.p / 100.0)
                        END AS expected_cost
                    FROM sale_order so
                    JOIN travel_trip t ON t.id = so.trip_id
                    JOIN res_company c ON c.id = so.company_id
                    CROSS JOIN LATERAL (
                        SELECT COALESCE(NULLIF(so.currency_rate, 0), 1.0) AS rate
                    ) cr
                    CROSS JOIN LATERAL (
                        SELECT CASE so.travel_booking_state
                            WHEN 'quotation' THEN 100.0 - COALESCE(c.travel_quotation_win_rate, 0)
                            WHEN 'pending' THEN COALESCE(c.travel_cancel_rate_pending, 0)
                            WHEN 'deposit' THEN COALESCE(c.travel_cancel_rate_deposit, 0)
                            WHEN 'paid' THEN COALESCE(c.travel_cancel_rate_paid, 0)
                            ELSE 100.0
                        END AS p
                    ) pr
                    CROSS JOIN LATERAL (
                        SELECT CASE
                            WHEN so.travel_booking_state = 'cancelled'
                                THEN COALESCE(so.travel_penalty_amount, 0) / cr.rate
                            ELSE so.amount_total / cr.rate * (1 - pr.p / 100.0)
                                 + LEAST(COALESCE(so.travel_amount_paid, 0),
                                         COALESCE(so.travel_deposit_required, 0))
                                   / cr.rate * (pr.p / 100.0)
                        END AS expected
                    ) rev
                    WHERE so.trip_id IS NOT NULL
                      AND so.travel_booking_state IS NOT NULL
                      AND t.state != 'cancel'
                      AND (so.travel_booking_state != 'quotation'
                           OR c.travel_forecast_include_quotations)
                ) b
            )
        """)
