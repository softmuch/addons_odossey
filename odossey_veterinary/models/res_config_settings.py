from odoo import _, api, fields, models


# Agenda options ticked by default: stored as 'True' / 'False' (a boolean config parameter set to False is deleted
# and would come back ticked)
AGENDA_FLAGS = ['vet_agenda_hide_closed_days', 'vet_agenda_card_species', 'vet_agenda_card_owner', 'vet_agenda_card_phone',
                'vet_agenda_card_veterinarian', 'vet_agenda_card_reason', 'vet_agenda_card_alerts',
                'vet_agenda_card_status']


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
    vet_resource_calendar_id = fields.Many2one(
        related='company_id.resource_calendar_id', readonly=False, string="Opening Hours",
        help="Working hours of the clinic: the agenda starts at the opening time and shades closed hours. "
             "Example: Monday to Friday 8:40-12:40 and 14:00-18:00.")
    vet_agenda_slot_minutes = fields.Integer(
        string="Agenda Slot (min)", config_parameter='odossey_veterinary.agenda_slot_minutes', default=15,
        help="Length of each row of the agenda and step of the time picker of the appointments; clicks and drags "
             "snap to it, counted from the opening time. Example: 20 → 8:40, 9:00, 9:20...")
    vet_agenda_default_scale = fields.Selection([
        ('day', "Day"), ('week', "Week"), ('month', "Month"),
    ], string="Agenda Opens On", config_parameter='odossey_veterinary.agenda_default_scale', default='day',
        help="View shown the first time a user opens the agenda; afterwards each user keeps the last one chosen. "
             "Example: Week → the reception sees Monday to Saturday at once.")
    vet_agenda_color_by = fields.Selection([
        ('vet_veterinarian_id', "Veterinarian"), ('vet_appointment_type_id', "Appointment Type"),
        ('vet_room_id', "Room"),
    ], string="Agenda Colors By", config_parameter='odossey_veterinary.agenda_color_by', default='vet_appointment_type_id',
        help="What the color of each appointment tells. Example: Veterinarian → every professional has a color "
             "(set in Configuration › Veterinarians).")
    vet_default_appointment_type_id = fields.Many2one(
        'vet.appointment.type', string="Default Appointment Type",
        config_parameter='odossey_veterinary.default_appointment_type_id',
        help="Type proposed when booking; its duration sets the length of the appointment. Example: Consultation (20 min).")
    group_vet_use_rooms = fields.Boolean(
        string="Book by Room", implied_group='odossey_veterinary.group_vet_use_rooms',
        help="Ask for a consulting room in every appointment. Untick it when the clinic books by veterinarian only.")
    vet_agenda_hide_closed_days = fields.Boolean(
        string="Hide Closed Days", default=True,
        help="Days without opening hours are not shown in the agenda, so the open days get wider columns. "
             "Example: Sunday closed → the week goes from Monday to Saturday.")
    vet_agenda_require_veterinarian = fields.Boolean(
        string="Veterinarian Required", config_parameter='odossey_veterinary.agenda_require_veterinarian',
        help="An appointment cannot be saved without the veterinarian who attends it.")
    vet_agenda_card_species = fields.Boolean(string="Species", default=True)
    vet_agenda_card_owner = fields.Boolean(string="Owner", default=True)
    vet_agenda_card_phone = fields.Boolean(string="Phone", default=True)
    vet_agenda_card_veterinarian = fields.Boolean(string="Veterinarian", default=True)
    vet_agenda_card_reason = fields.Boolean(string="Type and Reason", default=True)
    vet_agenda_card_alerts = fields.Boolean(string="Alerts", default=True)
    vet_agenda_card_status = fields.Boolean(string="Status", default=True)
    vet_agenda_row_height = fields.Selection([
        ('compact', "Compact"), ('comfortable', "Comfortable"), ('large', "Large"),
    ], string="Agenda Row Height", config_parameter='odossey_veterinary.agenda_row_height', default='comfortable',
        help="Height of each row of the agenda. Taller rows show patient, owner, phone, veterinarian and reason "
             "inside every appointment. Example: Comfortable → three lines in a 20-minute appointment.")

    @api.model
    def get_values(self):
        res = super().get_values()
        if not res.get('vet_hospitalization_product_id'):
            # show the service actually charged by default (see vet.hospitalization._get_day_product)
            product = self.env.ref('odossey_veterinary.product_service_hospitalization_day', raise_if_not_found=False)
            res['vet_hospitalization_product_id'] = product.id if product else False
        Event = self.env['calendar.event']
        for name in AGENDA_FLAGS:
            res[name] = Event._vet_agenda_param(name[4:], True)
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        for name in AGENDA_FLAGS:
            ICP.set_param('odossey_veterinary.%s' % name[4:], 'True' if self[name] else 'False')

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
