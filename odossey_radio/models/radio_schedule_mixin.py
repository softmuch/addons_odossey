from odoo import api, fields, models

RADIO_LINE_FIELDS = [
    'radio_program_id', 'radio_daypart_id', 'radio_break_id', 'radio_format_id',
    'radio_duration', 'radio_spots_per_day', 'radio_position', 'radio_date_from',
    'radio_date_to',
]


class RadioScheduleMixin(models.AbstractModel):
    """Airing plan of an advertising line (advertising order line and contract line)."""
    _name = 'radio.schedule.mixin'
    _description = "Radio Airing Plan"

    radio_line = fields.Boolean(compute='_compute_radio_line', string="Radio Line")
    radio_format_id = fields.Many2one('radio.ad.format', string="Format",
                                      compute='_compute_radio_from_product', store=True,
                                      readonly=False)
    radio_duration = fields.Integer(string="Seconds", compute='_compute_radio_from_product',
                                    store=True, readonly=False)
    radio_program_id = fields.Many2one('radio.program', string="Program",
                                       compute='_compute_radio_program', store=True,
                                       readonly=False)
    radio_daypart_id = fields.Many2one('radio.daypart', string="Daypart",
                                       compute='_compute_radio_daypart', store=True,
                                       readonly=False)
    radio_break_id = fields.Many2one(
        'radio.break', string="Fixed Break",
        domain="[('program_id', '=?', radio_program_id)]",
        help="Air always in this break (optional).")
    radio_spots_per_day = fields.Integer(string="Per Day", default=1)
    radio_weekday_ids = fields.Many2many('radio.weekday', string="Days",
                                         help="Days of airing (all the days if empty).")
    radio_position = fields.Selection(
        selection=[('any', "Any"), ('first', "First in break"), ('last', "Last in break")],
        string="Position", default='any')
    radio_date_from = fields.Date(string="From", help="Start of the airing (optional).")
    radio_date_to = fields.Date(string="Until", help="End of the airing (optional).")

    @api.depends('product_id.radio_ok')
    def _compute_radio_line(self):
        for line in self:
            line.radio_line = bool(line.product_id.radio_ok)

    # one compute per field: a value given for one of them must not block the others
    @api.depends('product_id')
    def _compute_radio_from_product(self):
        for line in self:
            product = line.product_id
            if product.radio_ok:
                line.radio_format_id = product.radio_format_id
                line.radio_duration = (product.radio_duration
                                       or product.radio_format_id.default_duration)
            else:
                line.radio_format_id = line.radio_format_id
                line.radio_duration = line.radio_duration

    @api.depends('product_id')
    def _compute_radio_program(self):
        for line in self:
            line.radio_program_id = line.product_id.radio_program_id or line.radio_program_id

    @api.depends('product_id')
    def _compute_radio_daypart(self):
        for line in self:
            line.radio_daypart_id = line.product_id.radio_daypart_id or line.radio_daypart_id

    def _radio_weekday_codes(self):
        self.ensure_one()
        return set(self.radio_weekday_ids.mapped('code')) or set(range(7))

    def _radio_monthly_estimate(self, months=1):
        """Airings in `months` months according to the days and spots per day."""
        self.ensure_one()
        days = len(self._radio_weekday_codes())
        return round(self.radio_spots_per_day * days * 52 / 12 * months)

    def _radio_plan_description(self):
        self.ensure_one()
        parts = []
        if self.radio_program_id:
            parts.append(self.radio_program_id.name)
        elif self.radio_daypart_id:
            parts.append(self.radio_daypart_id.display_name)
        if self.radio_spots_per_day:
            days = self.radio_weekday_ids.sorted('sequence').mapped('name')
            parts.append(self.env._("%(spots)s per day, %(days)s", spots=self.radio_spots_per_day,
                                    days=", ".join(days) if days else self.env._("every day")))
        if self.radio_duration:
            parts.append(f"{self.radio_duration}\"")
        return " - ".join(parts)
