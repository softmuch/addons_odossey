from odoo import api, fields, models


class TravelCancellationPolicy(models.Model):
    _name = 'travel.cancellation.policy'
    _description = "Travel Cancellation Policy"
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string="Company")
    deposit_refundable = fields.Boolean(
        string="Refundable Deposit",
        help="If unchecked, the deposit is always retained when the passenger cancels.")
    rule_ids = fields.One2many('travel.cancellation.rule', 'policy_id', string="Rules", copy=True)
    note = fields.Html(string="Conditions", translate=True)

    def _get_penalty_percent(self, days_before):
        """Penalty (% of the booking total) when cancelling ``days_before`` days before
        departure. Rules are evaluated from the closest to the departure."""
        self.ensure_one()
        for rule in self.rule_ids.sorted('days_before'):
            if days_before <= rule.days_before:
                return rule.penalty_percent
        return 0.0


class TravelCancellationRule(models.Model):
    _name = 'travel.cancellation.rule'
    _description = "Travel Cancellation Rule"
    _order = 'days_before'

    policy_id = fields.Many2one('travel.cancellation.policy', required=True, ondelete='cascade')
    days_before = fields.Integer(
        string="Up to Days Before Departure", required=True,
        help="The rule applies when the cancellation happens this number of days before the "
             "departure or less.")
    penalty_percent = fields.Float(string="Penalty (%)", required=True)

    _penalty_range = models.Constraint(
        'CHECK(penalty_percent >= 0 AND penalty_percent <= 100)',
        "The penalty must be between 0 and 100%.")

    @api.depends('days_before', 'penalty_percent')
    def _compute_display_name(self):
        for rule in self:
            rule.display_name = self.env._("≤ %(days)s days: %(percent)s%%",
                                           days=rule.days_before, percent=rule.penalty_percent)
