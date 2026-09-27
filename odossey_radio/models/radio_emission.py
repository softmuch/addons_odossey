from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .radio_program import format_float_time


class RadioEmission(models.Model):
    """One airing of an advertising item in the daily log (pauta)."""
    _name = 'radio.emission'
    _description = "Spot Airing (Daily Log)"
    _order = 'date, planned_time, sequence, id'
    _rec_name = 'display_name'

    date = fields.Date(required=True, index=True)
    break_id = fields.Many2one('radio.break', string="Break", index=True, ondelete='restrict')
    program_id = fields.Many2one('radio.program', string="Program", index=True,
                                 ondelete='restrict')
    planned_time = fields.Float(string="Time")
    planned_datetime = fields.Datetime(string="Scheduled", compute='_compute_planned_datetime',
                                       store=True)
    sequence = fields.Integer(default=10, help="Order inside the break.")
    subscription_id = fields.Many2one('sale.subscription', string="Contract", required=True,
                                      index=True, ondelete='cascade')
    subscription_line_id = fields.Many2one('sale.subscription.line', string="Contract Line",
                                           index=True, ondelete='cascade')
    partner_id = fields.Many2one(related='subscription_id.partner_id', store=True,
                                 string="Advertiser", index=True)
    agency_id = fields.Many2one(related='subscription_id.radio_agency_id', store=True,
                                string="Agency")
    company_id = fields.Many2one(related='subscription_id.company_id', store=True, index=True)
    product_id = fields.Many2one(related='subscription_line_id.product_id', store=True)
    format_id = fields.Many2one('radio.ad.format', string="Format", required=True)
    format_kind = fields.Selection(related='format_id.kind')
    material_id = fields.Many2one('radio.material', string="Material")
    material_missing = fields.Boolean(compute='_compute_material_missing', store=True,
                                      string="Material Missing")
    duration = fields.Integer(string="Duration (s)")
    state = fields.Selection(
        selection=[
            ('planned', "Planned"),
            ('aired', "Aired"),
            ('missed', "Not aired"),
            ('conflict', "No room"),
            ('cancelled', "Cancelled"),
        ], default='planned', required=True, index=True)
    aired_at = fields.Datetime(string="Aired At")
    aired_by = fields.Many2one('res.users', string="Confirmed By")
    note = fields.Char(string="Note / Reason")
    compensation_of_id = fields.Many2one('radio.emission', string="Compensates",
                                         help="Spot not aired that this airing replaces.")
    invoice_id = fields.Many2one('account.move', string="Invoice", copy=False,
                                 help="Invoice of the period that billed this airing.")
    time_label = fields.Char(compute='_compute_time_label', string="Hour")

    @api.depends('date', 'planned_time', 'break_id')
    def _compute_planned_datetime(self):
        for emission in self:
            if emission.date and emission.break_id:
                emission.planned_datetime = emission.break_id._datetime(emission.date)
            else:
                emission.planned_datetime = False

    @api.depends('material_id', 'format_id.requires_material')
    def _compute_material_missing(self):
        for emission in self:
            emission.material_missing = bool(emission.format_id.requires_material
                                             and not emission.material_id)

    @api.depends('planned_time')
    def _compute_time_label(self):
        for emission in self:
            emission.time_label = format_float_time(emission.planned_time or 0.0)

    @api.depends('subscription_id', 'date', 'planned_time')
    def _compute_display_name(self):
        for emission in self:
            emission.display_name = " - ".join(filter(None, [
                emission.date and fields.Date.to_string(emission.date),
                emission.time_label,
                emission.partner_id.name,
                emission.format_id.name,
            ]))

    # ------------------------------------------------------------------
    # Broadcast control
    # ------------------------------------------------------------------
    def action_mark_aired(self):
        todo = self.filtered(lambda e: e.state in ('planned', 'missed'))
        if self - todo - self.filtered(lambda e: e.state == 'aired'):
            raise UserError(self.env._("Only planned spots can be marked as aired."))
        for emission in todo:
            emission.write({
                'state': 'aired',
                'aired_at': emission.planned_datetime or fields.Datetime.now(),
                'aired_by': self.env.user.id,
            })
        return True

    def action_mark_missed(self):
        todo = self.filtered(lambda e: e.state in ('planned', 'aired'))
        if todo.filtered('invoice_id'):
            raise UserError(self.env._("An invoiced spot cannot be changed."))
        todo.write({'state': 'missed', 'aired_at': False, 'aired_by': self.env.user.id})
        return True

    def action_reset(self):
        if self.filtered('invoice_id'):
            raise UserError(self.env._("An invoiced spot cannot be changed."))
        self.write({'state': 'planned', 'aired_at': False, 'aired_by': False})
        return True

    def action_compensate(self):
        """Reschedule the spots not aired in the next break with room (same day, else the
        following days)."""
        created = self.env['radio.emission']
        for emission in self.filtered(lambda e: e.state in ('missed', 'conflict')):
            if emission.compensation_ids.filtered(lambda c: c.state != 'cancelled'):
                continue
            line = emission.subscription_line_id
            if not line:
                continue
            for offset in range(0, 8):
                day = emission.date + timedelta(days=offset)
                after = emission.planned_time if offset == 0 else -1
                new = emission.subscription_id._radio_plan_extra(line, day, after, emission)
                if new:
                    created |= new
                    break
            else:
                emission.note = self.env._("No room to compensate in the next 7 days.")
        return self._action_open(created) if created else True

    compensation_ids = fields.One2many('radio.emission', 'compensation_of_id',
                                       string="Compensations")

    def _action_open(self, emissions):
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_radio.radio_emission_action')
        action['domain'] = [('id', 'in', emissions.ids)]
        action['context'] = {}
        return action

    @api.model
    def _cron_confirm_past(self):
        """End of day: planned spots of the past days are considered aired (the operator
        records the exceptions)."""
        today = fields.Date.context_today(self)
        for company in self.env['res.company'].sudo().search([('radio_auto_confirm', '=', True)]):
            emissions = self.sudo().with_company(company).search([
                ('company_id', '=', company.id), ('state', '=', 'planned'), ('date', '<', today)])
            for emission in emissions:
                emission.write({'state': 'aired',
                                'aired_at': emission.planned_datetime or fields.Datetime.now()})
