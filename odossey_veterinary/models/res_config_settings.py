from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    vet_due_soon_days = fields.Integer(
        string="'Due Soon' Window (days)", config_parameter='odossey_veterinary.due_soon_days', default=30,
        help="A vaccine or antiparasitic is shown as 'Due soon' this many days before its due date. "
             "Example: 30 → a rabies booster due on 30/11 turns orange from 31/10.")
    vet_reminder_days = fields.Integer(
        string="Send Reminders (days before)", config_parameter='odossey_veterinary.reminder_days', default=7,
        help="The daily reminder email is sent to the owner this many days before the due date (overdue items are "
             "included too). Example: 7 → for a vaccine due on Friday 14, the owner receives the email on Friday 7.")
    vet_auto_sale_order = fields.Boolean(
        string="Create Sale Order When Closing a Consultation", config_parameter='odossey_veterinary.auto_sale_order', default=True,
        help="When the veterinarian closes a consultation, its charges become a quotation for the owner, ready to "
             "confirm and invoice at the reception. Example: consultation + rabies vaccine → quotation with 2 lines.")
    vet_hospitalization_product_id = fields.Many2one(
        'product.product', string="Hospitalization Day Service", config_parameter='odossey_veterinary.hospitalization_product_id',
        help="Service charged for each started day of hospitalization. Example: admitted Monday 18:00, discharged "
             "Wednesday 10:00 → 2 days.")
    vet_demo_loaded = fields.Boolean(compute='_compute_vet_demo_loaded')

    @api.model
    def get_values(self):
        res = super().get_values()
        if not res.get('vet_hospitalization_product_id'):
            # show the service actually charged by default (see vet.hospitalization._get_day_product)
            product = self.env.ref('odossey_veterinary.product_service_hospitalization_day', raise_if_not_found=False)
            res['vet_hospitalization_product_id'] = product.id if product else False
        return res

    def _compute_vet_demo_loaded(self):
        loaded = bool(self.env['ir.config_parameter'].sudo().get_param('odossey_veterinary.demo_loaded'))
        for rec in self:
            rec.vet_demo_loaded = loaded

    def action_vet_load_demo(self):
        self.env['vet.demo'].load_demo()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'success', 'sticky': False, 'message': _("Demo data loaded: owners, patients, consultations, "
                                                                        "vaccinations, prescriptions and a hospitalization."),
                       'next': {'type': 'ir.actions.client', 'tag': 'reload'}},
        }
