from odoo import api, fields, models
from odoo.exceptions import UserError


class RadioMaterial(models.Model):
    """Advertising material: recorded audio of a spot or script of a live mention."""
    _name = 'radio.material'
    _description = "Advertising Material"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_to desc, id desc'

    name = fields.Char(required=True, tracking=True)
    subscription_id = fields.Many2one('sale.subscription', string="Contract", required=True,
                                      ondelete='cascade', index=True)
    partner_id = fields.Many2one(related='subscription_id.partner_id', store=True,
                                 string="Advertiser")
    company_id = fields.Many2one(related='subscription_id.company_id', store=True, index=True)
    format_id = fields.Many2one('radio.ad.format', string="Format",
                                help="Leave empty to use it for any format of the contract.")
    kind = fields.Selection(
        selection=[('audio', "Recorded audio"), ('script', "Script (live mention)")],
        required=True, default='audio')
    audio_file = fields.Binary(string="Audio", attachment=True)
    audio_filename = fields.Char()
    script = fields.Html(string="Script", help="Text read by the host (mentions, PNT).")
    duration = fields.Integer(string="Duration (s)", default=30)
    date_from = fields.Date(string="Valid From", default=fields.Date.context_today)
    date_to = fields.Date(string="Valid Until")
    restriction = fields.Selection(
        selection=[
            ('none', "None"),
            ('alcohol', "Alcoholic beverages"),
            ('tobacco', "Tobacco"),
            ('health', "Health / medicines / aesthetics"),
            ('gambling', "Gambling"),
            ('minors', "Aimed at minors"),
        ], string="Restricted Content", default='none', required=True,
        help="Advertising with legal restrictions (Law 26.522, art. 81) needs an "
             "authorization before being aired.")
    authorization_ref = fields.Char(string="Authorization",
                                    help="Number of the authorization of the competent body.")
    state = fields.Selection(
        selection=[('draft', "To approve"), ('approved', "Approved"), ('expired', "Expired")],
        default='draft', required=True, tracking=True)
    sequence = fields.Integer(default=10, help="Rotation order between the valid materials.")
    note = fields.Text()
    emission_count = fields.Integer(compute='_compute_emission_count', string="Spots")

    def _compute_emission_count(self):
        data = self.env['radio.emission']._read_group(
            [('material_id', 'in', self.ids), ('state', '!=', 'cancelled')],
            ['material_id'], ['__count'])
        counts = {material.id: count for material, count in data}
        for material in self:
            material.emission_count = counts.get(material.id, 0)

    @api.onchange('kind')
    def _onchange_kind(self):
        if self.kind == 'script' and not self.format_id:
            self.format_id = self.env['radio.ad.format'].search([('kind', '=', 'mention')], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        materials = super().create(vals_list)
        materials.filtered(lambda m: m.state == 'approved')._assign_to_planned()
        return materials

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') == 'approved' or {'date_from', 'date_to', 'format_id'} & set(vals):
            self.filtered(lambda m: m.state == 'approved')._assign_to_planned()
        return res

    def _assign_to_planned(self):
        """Give the material to the planned spots of its contract that have none."""
        for material in self:
            emissions = self.env['radio.emission'].search([
                ('subscription_id', '=', material.subscription_id.id),
                ('state', 'in', ('planned', 'conflict')), ('material_id', '=', False),
            ])
            emissions.filtered(
                lambda e, m=material: m._is_valid(e.date)
                and (not m.format_id or m.format_id == e.format_id)
            ).write({'material_id': material.id})

    def action_approve(self):
        for material in self:
            if material.restriction != 'none' and not material.authorization_ref:
                raise UserError(self.env._(
                    "The material %s has restricted content: enter the authorization before "
                    "approving it.", material.name))
            if material.kind == 'audio' and not material.audio_file:
                raise UserError(self.env._("Upload the audio of %s before approving it.",
                                           material.name))
            if material.kind == 'script' and not material.script:
                raise UserError(self.env._("Write the script of %s before approving it.",
                                           material.name))
        self.write({'state': 'approved'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def _is_valid(self, day):
        self.ensure_one()
        return (self.state == 'approved'
                and (not self.date_from or self.date_from <= day)
                and (not self.date_to or day <= self.date_to))

    @api.model
    def _cron_expire(self):
        today = fields.Date.context_today(self)
        self.search([('state', '=', 'approved'), ('date_to', '<', today)]).write(
            {'state': 'expired'})
