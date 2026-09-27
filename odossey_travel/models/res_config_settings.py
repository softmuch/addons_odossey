from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    travel_cancel_rate_pending = fields.Float(
        related='company_id.travel_cancel_rate_pending', readonly=False)
    travel_cancel_rate_deposit = fields.Float(
        related='company_id.travel_cancel_rate_deposit', readonly=False)
    travel_cancel_rate_paid = fields.Float(
        related='company_id.travel_cancel_rate_paid', readonly=False)
    travel_forecast_include_quotations = fields.Boolean(
        related='company_id.travel_forecast_include_quotations', readonly=False)
    travel_quotation_win_rate = fields.Float(
        related='company_id.travel_quotation_win_rate', readonly=False)
    travel_historical_cancel_rate = fields.Float(
        string="Historical Cancellation Rate (%)", compute='_compute_travel_historical_cancel_rate',
        help="Cancelled bookings / confirmed bookings of the trips already completed.")
    travel_iibb_rate = fields.Float(related='company_id.travel_iibb_rate', readonly=False)
    travel_iibb_base = fields.Selection(related='company_id.travel_iibb_base', readonly=False)
    travel_payment_fee_rate = fields.Float(
        related='company_id.travel_payment_fee_rate', readonly=False)
    travel_passport_validity_months = fields.Integer(
        related='company_id.travel_passport_validity_months', readonly=False)
    travel_invoice_service_dates = fields.Selection(
        related='company_id.travel_invoice_service_dates', readonly=False)
    travel_file_number = fields.Char(related='company_id.travel_file_number', readonly=False)
    travel_birthday_enabled = fields.Boolean(
        related='company_id.travel_birthday_enabled', readonly=False)
    travel_birthday_template_id = fields.Many2one(
        related='company_id.travel_birthday_template_id', readonly=False)

    @api.depends('company_id')
    def _compute_travel_historical_cancel_rate(self):
        for settings in self:
            settings.travel_historical_cancel_rate = self.env['sale.order'].with_company(
                settings.company_id)._travel_historical_cancel_rate()

    def action_travel_apply_historical_rate(self):
        self.ensure_one()
        rate = self.travel_historical_cancel_rate
        self.company_id.write({
            'travel_cancel_rate_pending': rate,
            'travel_cancel_rate_deposit': rate,
            'travel_cancel_rate_paid': rate,
        })
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_travel_open_birthday_template(self):
        self.ensure_one()
        template = self.travel_birthday_template_id or self.env.ref(
            'odossey_travel.mail_template_birthday', raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.template',
            'res_id': template.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_travel_load_demo(self):
        self.ensure_one()
        return self.env['travel.trip'].with_company(self.company_id)._travel_load_demo_data()
