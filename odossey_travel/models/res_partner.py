import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # personal data of the travellers: travel users only
    birthdate = fields.Date(string="Birthdate", tracking=True, groups='odossey_travel.group_travel_user')
    birthday_month = fields.Integer(
        string="Birthday Month", compute='_compute_birthday_parts', store=True)
    birthday_day = fields.Integer(
        string="Birthday Day", compute='_compute_birthday_parts', store=True)
    age = fields.Integer(string="Age", compute='_compute_age', groups='odossey_travel.group_travel_user')
    gender = fields.Selection(
        selection=[('male', "Male"), ('female', "Female"), ('other', "Other")],
        string="Gender")
    nationality_id = fields.Many2one('res.country', string="Nationality")
    passport_number = fields.Char(string="Passport Number", groups='odossey_travel.group_travel_user')
    passport_country_id = fields.Many2one('res.country', string="Passport Issuing Country",
                                          groups='odossey_travel.group_travel_user')
    passport_issue_date = fields.Date(string="Passport Issue Date", groups='odossey_travel.group_travel_user')
    passport_expiry_date = fields.Date(string="Passport Expiry Date", groups='odossey_travel.group_travel_user')
    passport_expired = fields.Boolean(
        string="Passport Expired", compute='_compute_passport_expired',
        search='_search_passport_expired', groups='odossey_travel.group_travel_user')
    dni_tramite = fields.Char(
        string="DNI Procedure Number", groups='odossey_travel.group_travel_user',
        help="Número de trámite printed on the Argentine DNI card.")
    dni_ejemplar = fields.Char(string="DNI Copy", groups='odossey_travel.group_travel_user',
                               help="Ejemplar (A, B, C...) of the DNI card.")
    emergency_contact_name = fields.Char(string="Emergency Contact", groups='odossey_travel.group_travel_user')
    emergency_contact_phone = fields.Char(string="Emergency Phone", groups='odossey_travel.group_travel_user')
    travel_dietary_notes = fields.Char(string="Dietary Restrictions", groups='odossey_travel.group_travel_user')
    travel_medical_notes = fields.Text(string="Medical Notes", groups='odossey_travel.group_travel_user')
    travel_birthday_optout = fields.Boolean(
        string="No Birthday Email",
        help="Do not send the automatic birthday greeting to this contact.")
    travel_birthday_last_sent = fields.Date(string="Last Birthday Email", readonly=True, copy=False)
    travel_passenger_ids = fields.One2many('travel.passenger', 'partner_id', string="Trips")
    travel_trip_count = fields.Integer(string="Trip Count", compute='_compute_travel_trip_count')

    @api.depends('birthdate')
    def _compute_birthday_parts(self):
        for partner in self:
            partner.birthday_month = partner.birthdate.month if partner.birthdate else 0
            partner.birthday_day = partner.birthdate.day if partner.birthdate else 0

    @api.depends('birthdate')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for partner in self:
            partner.age = relativedelta(today, partner.birthdate).years if partner.birthdate else 0

    @api.depends('passport_expiry_date')
    def _compute_passport_expired(self):
        today = fields.Date.context_today(self)
        for partner in self:
            partner.passport_expired = bool(
                partner.passport_expiry_date and partner.passport_expiry_date < today)

    def _search_passport_expired(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            return NotImplemented
        today = fields.Date.context_today(self)
        expired = (operator == '=') == value
        if expired:
            return [('passport_expiry_date', '<', today)]
        return ['|', ('passport_expiry_date', '=', False), ('passport_expiry_date', '>=', today)]

    def _compute_travel_trip_count(self):
        data = self.env['travel.passenger']._read_group(
            [('partner_id', 'in', self.ids), ('state', '!=', 'cancelled')],
            ['partner_id'], ['trip_id:count_distinct'])
        counts = {partner.id: count for partner, count in data}
        for partner in self:
            partner.travel_trip_count = counts.get(partner.id, 0)

    def action_view_travel_passengers(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_travel.travel_passenger_action')
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action

    def action_travel_scan_document(self):
        self.ensure_one()
        return self.env['travel.document.scan'].action_open(partner=self)

    # ------------------------------------------------------------------
    # Birthday emails
    # ------------------------------------------------------------------
    def _travel_birthday_domain(self, date):
        domain = [
            ('birthday_month', '=', date.month),
            ('email', '!=', False),
            ('travel_birthday_optout', '=', False),
            '|', ('travel_birthday_last_sent', '=', False),
            ('travel_birthday_last_sent', '<', date.replace(month=1, day=1)),
        ]
        if date.month == 2 and date.day == 28 and not self._is_leap_year(date.year):
            # people born on February 29th are greeted on the 28th in non leap years
            domain.append(('birthday_day', 'in', [28, 29]))
        else:
            domain.append(('birthday_day', '=', date.day))
        return domain

    @staticmethod
    def _is_leap_year(year):
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

    @api.model
    def _cron_travel_send_birthday_emails(self):
        today = fields.Date.context_today(self)
        default_template = self.env.ref('odossey_travel.mail_template_birthday',
                                        raise_if_not_found=False)
        for company in self.env['res.company'].sudo().search(
                [('travel_birthday_enabled', '=', True)]):
            template = (company.travel_birthday_template_id or default_template).sudo()
            if not template:
                continue
            partners = self.sudo().with_company(company).search(
                self._travel_birthday_domain(today)
                + [('company_id', 'in', [False, company.id])])
            # never write to blacklisted addresses
            partners = partners.filtered(lambda p: not p.is_blacklisted)
            sent = 0
            for partner in partners:
                try:
                    with self.env.cr.savepoint():
                        template.with_company(company).send_mail(
                            partner.id, email_layout_xmlid='mail.mail_notification_light')
                        partner.travel_birthday_last_sent = today
                    sent += 1
                except Exception:
                    _logger.exception("Travel: birthday email to partner %s failed", partner.id)
            _logger.info("Travel: %s birthday emails sent for company %s",
                         sent, company.name)
        return True
