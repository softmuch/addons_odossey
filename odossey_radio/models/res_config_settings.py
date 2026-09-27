from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    radio_frequency = fields.Char(related='company_id.radio_frequency', readonly=False)
    radio_signal = fields.Char(related='company_id.radio_signal', readonly=False)
    radio_license = fields.Char(related='company_id.radio_license', readonly=False)
    radio_band = fields.Selection(related='company_id.radio_band', readonly=False)
    radio_enacom_category = fields.Selection(related='company_id.radio_enacom_category',
                                             readonly=False)
    radio_enacom_rate = fields.Float(related='company_id.radio_enacom_rate', readonly=False)
    radio_max_ad_minutes = fields.Float(related='company_id.radio_max_ad_minutes', readonly=False)
    radio_break_capacity = fields.Integer(related='company_id.radio_break_capacity', readonly=False)
    radio_break_interval = fields.Integer(related='company_id.radio_break_interval', readonly=False)
    radio_break_offset = fields.Integer(related='company_id.radio_break_offset', readonly=False)
    radio_schedule_days = fields.Integer(related='company_id.radio_schedule_days', readonly=False)
    radio_auto_confirm = fields.Boolean(related='company_id.radio_auto_confirm', readonly=False)
    radio_suspend_days = fields.Integer(related='company_id.radio_suspend_days', readonly=False)
    radio_agency_commission_product_id = fields.Many2one(
        related='company_id.radio_agency_commission_product_id', readonly=False)
    radio_certificate_note = fields.Html(related='company_id.radio_certificate_note',
                                         readonly=False)

    def action_radio_load_demo(self):
        self.ensure_one()
        return self.env['radio.program'].with_company(self.company_id)._radio_load_demo_data()
