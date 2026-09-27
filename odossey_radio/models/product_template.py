from odoo import api, fields, models


class ProductTemplate(models.Model):
    """Rate card: an advertising product is a format (spot, mention...) of a given
    duration, optionally for a daypart or a program, priced per unit aired."""
    _inherit = 'product.template'

    radio_ok = fields.Boolean(string="Radio Advertising",
                              help="Product of the radio rate card.")
    radio_format_id = fields.Many2one('radio.ad.format', string="Advertising Format")
    radio_duration = fields.Integer(string="Duration (s)",
                                    help="Duration of the spot or mention, in seconds.")
    radio_daypart_id = fields.Many2one('radio.daypart', string="Daypart")
    radio_program_id = fields.Many2one('radio.program', string="Program",
                                       help="Rate of a specific program (optional).")

    @api.onchange('radio_format_id')
    def _onchange_radio_format_id(self):
        if self.radio_format_id and not self.radio_duration:
            self.radio_duration = self.radio_format_id.default_duration

    @api.onchange('radio_ok')
    def _onchange_radio_ok(self):
        if self.radio_ok:
            self.type = 'service'
            self.subscribable = True
            if not self.subscription_template_id:
                self.subscription_template_id = self.env['sale.subscription.template'].search(
                    [('radio_template', '=', True)], limit=1)
