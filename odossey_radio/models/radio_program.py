from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import ValidationError


def float_to_time(value):
    """8.5 -> time(8, 30); 24.0 -> time(23, 59, 59)."""
    if value >= 24:
        return time(23, 59, 59)
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    if minutes == 60:
        hours, minutes = hours + 1, 0
    return time(min(hours, 23), minutes)


def format_float_time(value):
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    if minutes == 60:
        hours, minutes = hours + 1, 0
    return f"{hours:02d}:{minutes:02d}"


class RadioWeekday(models.Model):
    _name = 'radio.weekday'
    _description = "Day of the Week"
    _order = 'sequence'

    name = fields.Char(required=True, translate=True)
    code = fields.Integer(required=True, help="0 = Monday ... 6 = Sunday (Python weekday).")
    sequence = fields.Integer()

    _code_unique = models.Constraint('UNIQUE(code)', "Each day of the week exists once.")


class RadioDaypart(models.Model):
    """Time band of the rate card (central / afternoon / night / late night)."""
    _name = 'radio.daypart'
    _description = "Daypart"
    _order = 'sequence, hour_from'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    hour_from = fields.Float(string="From", required=True)
    hour_to = fields.Float(string="To", required=True)
    color = fields.Integer()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.constrains('hour_from', 'hour_to')
    def _check_hours(self):
        for daypart in self:
            if not 0 <= daypart.hour_from < daypart.hour_to <= 24:
                raise ValidationError(self.env._(
                    "The daypart %s must start before it ends, between 00:00 and 24:00.",
                    daypart.name))

    @api.depends('name', 'hour_from', 'hour_to')
    def _compute_display_name(self):
        for daypart in self:
            daypart.display_name = (f"{daypart.name} ({format_float_time(daypart.hour_from)}-"
                                    f"{format_float_time(daypart.hour_to)})")

    def _contains(self, hour):
        self.ensure_one()
        return self.hour_from <= hour < self.hour_to


class RadioAdFormat(models.Model):
    """Advertising format: spot, mention, PNT, sponsorship, jingle, micro program..."""
    _name = 'radio.ad.format'
    _description = "Advertising Format"
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    sequence = fields.Integer(default=10)
    kind = fields.Selection(
        selection=[
            ('spot', "Recorded spot"),
            ('mention', "Live mention"),
            ('pnt', "PNT / Advertorial"),
            ('sponsorship', "Sponsorship"),
            ('jingle', "Jingle / Station ID"),
            ('micro', "Micro program"),
            ('digital', "Streaming / Digital"),
        ], required=True, default='spot')
    default_duration = fields.Integer(string="Default Duration (s)", default=30)
    uses_break = fields.Boolean(
        string="Uses Break Time", default=True,
        help="The format is aired inside a commercial break and uses its capacity "
             "(recorded spots). Live mentions and PNT are aired by the host during the "
             "program.")
    counts_ad_time = fields.Boolean(
        string="Counts as Advertising Time", default=True,
        help="Counts for the legal limit of advertising minutes per hour.")
    requires_material = fields.Boolean(
        string="Requires Material", default=True,
        help="A recorded audio (spot) or a script (mention) is needed before airing.")
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)


class RadioProgram(models.Model):
    _name = 'radio.program'
    _description = "Radio Program"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = 'hour_from, name'

    name = fields.Char(required=True, tracking=True, translate=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
    color = fields.Integer()
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    genre = fields.Selection(
        selection=[
            ('news', "News"),
            ('magazine', "Magazine"),
            ('sports', "Sports"),
            ('music', "Music"),
            ('entertainment', "Entertainment"),
            ('culture', "Culture / Education"),
            ('religious', "Religious"),
            ('other', "Other"),
        ], default='magazine', required=True)
    description = fields.Html(translate=True)
    host_ids = fields.Many2many(
        'res.partner', 'radio_program_host_rel', 'program_id', 'partner_id', string="Hosts",
        domain="[('radio_is_host', '=', True)]")
    producer_id = fields.Many2one('res.partner', string="Producer")
    operator_id = fields.Many2one('res.users', string="On-air Operator")
    weekday_ids = fields.Many2many('radio.weekday', string="Days", required=True)
    hour_from = fields.Float(string="Start", required=True, default=8.0)
    hour_to = fields.Float(string="End", required=True, default=10.0)
    duration = fields.Float(string="Duration (h)", compute='_compute_duration', store=True)
    daypart_id = fields.Many2one('radio.daypart', string="Daypart", compute='_compute_daypart',
                                 store=True, readonly=False)
    audience = fields.Char(string="Audience / Rating",
                           help="Audience measurement or estimated listeners (informative).")
    break_ids = fields.One2many('radio.break', 'program_id', string="Commercial Breaks")
    break_count = fields.Integer(compute='_compute_break_stats', string="Breaks per Show")
    break_capacity = fields.Integer(
        compute='_compute_break_stats', string="Break Capacity per Show (s)")
    sponsor_ids = fields.Many2many(
        'sale.subscription', string="Sponsors", compute='_compute_sponsor_ids',
        help="Contracts with a sponsorship of the program in progress.")
    emission_count = fields.Integer(compute='_compute_emission_count', string="Spots")
    grid_label = fields.Char(compute='_compute_grid_label')

    @api.constrains('hour_from', 'hour_to')
    def _check_hours(self):
        for program in self:
            if not 0 <= program.hour_from < program.hour_to <= 24:
                raise ValidationError(self.env._(
                    "The program %s must start before it ends, between 00:00 and 24:00.",
                    program.name))

    @api.depends('hour_from', 'hour_to')
    def _compute_duration(self):
        for program in self:
            program.duration = max(program.hour_to - program.hour_from, 0.0)

    @api.depends('hour_from')
    def _compute_daypart(self):
        dayparts = self.env['radio.daypart'].search([])
        for program in self:
            program.daypart_id = dayparts.filtered(lambda d: d._contains(program.hour_from))[:1]

    @api.depends('break_ids.capacity')
    def _compute_break_stats(self):
        for program in self:
            program.break_count = len(program.break_ids)
            program.break_capacity = sum(program.break_ids.mapped('capacity'))

    def _compute_sponsor_ids(self):
        Line = self.env['sale.subscription.line']
        for program in self:
            lines = Line.search([
                ('radio_program_id', '=', program.id),
                ('radio_format_id.kind', '=', 'sponsorship'),
                ('sale_subscription_id.in_progress', '=', True),
            ])
            program.sponsor_ids = lines.sale_subscription_id

    def _compute_emission_count(self):
        data = self.env['radio.emission']._read_group(
            [('program_id', 'in', self.ids), ('state', '!=', 'cancelled')],
            ['program_id'], ['__count'])
        counts = {program.id: count for program, count in data}
        for program in self:
            program.emission_count = counts.get(program.id, 0)

    @api.depends('weekday_ids', 'hour_from', 'hour_to')
    def _compute_grid_label(self):
        for program in self:
            days = ", ".join(program.weekday_ids.sorted('sequence').mapped('name'))
            program.grid_label = (f"{days} {format_float_time(program.hour_from)}-"
                                  f"{format_float_time(program.hour_to)}")

    def _airs_on(self, day):
        self.ensure_one()
        return day.weekday() in self.weekday_ids.mapped('code')

    def action_generate_breaks(self):
        """Create a commercial break every N minutes during the program (replaces the
        breaks without spots)."""
        company = self.env.company
        interval = company.radio_break_interval or 30
        offset = company.radio_break_offset or 25
        capacity = company.radio_break_capacity or 180
        for program in self:
            used = program.break_ids.filtered(lambda b: b.emission_ids)
            (program.break_ids - used).unlink()
            minute = program.hour_from * 60 + offset
            commands = []
            while minute < program.hour_to * 60:
                hour = minute / 60.0
                if not used.filtered(lambda b, h=hour: abs(b.time - h) < 1 / 120):
                    commands.append(fields.Command.create({'time': hour, 'capacity': capacity}))
                minute += interval
            program.break_ids = commands
        return True

    def action_view_emissions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_radio.radio_emission_action')
        action['domain'] = [('program_id', '=', self.id)]
        action['context'] = {'search_default_upcoming': 1}
        return action

    @api.model
    def _grid_data(self):
        """Weekly grid: {weekday record: [programs sorted by start]}."""
        weekdays = self.env['radio.weekday'].search([])
        programs = self.search([])
        return [(day, programs.filtered(lambda p, d=day: d in p.weekday_ids).sorted('hour_from'))
                for day in weekdays]


class RadioBreak(models.Model):
    """Commercial break (tanda) of a program, repeated every day the program airs."""
    _name = 'radio.break'
    _description = "Commercial Break"
    _order = 'program_id, time'

    name = fields.Char(compute='_compute_name', store=True)
    program_id = fields.Many2one('radio.program', string="Program", required=True,
                                 ondelete='cascade', index=True)
    company_id = fields.Many2one(related='program_id.company_id', store=True, index=True)
    time = fields.Float(string="Time", required=True)
    capacity = fields.Integer(string="Capacity (s)", default=180, required=True,
                              help="Seconds of advertising available in the break.")
    sequence = fields.Integer(default=10)
    emission_ids = fields.One2many('radio.emission', 'break_id', string="Spots")

    @api.depends('program_id.name', 'time')
    def _compute_name(self):
        for brk in self:
            brk.name = f"{format_float_time(brk.time)} {brk.program_id.name or ''}".strip()

    @api.constrains('time', 'program_id')
    def _check_time(self):
        for brk in self:
            if not brk.program_id.hour_from <= brk.time < brk.program_id.hour_to:
                raise ValidationError(self.env._(
                    "The break at %(time)s is outside the program %(program)s.",
                    time=format_float_time(brk.time), program=brk.program_id.name))

    def _datetime(self, day):
        """UTC naive datetime of the break on `day` (local time of the company)."""
        self.ensure_one()
        tz = pytz.timezone(self.env.user.tz or 'America/Argentina/Buenos_Aires')
        local = tz.localize(datetime.combine(day, float_to_time(self.time)))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    @staticmethod
    def _days(date_from, date_to):
        day = date_from
        while day <= date_to:
            yield day
            day += timedelta(days=1)
