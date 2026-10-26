import re
from datetime import datetime, time, timedelta
from urllib.parse import quote

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date, format_datetime


class ResPartner(models.Model):
    _inherit = 'res.partner'

    oph_recall_sent_for = fields.Date(string="Recall Sent For", copy=False,
                                      help="Control date for which the recall email was already sent.")

    def _oph_whatsapp_number(self):
        self.ensure_one()
        raw = self.phone or ''
        digits = re.sub(r'\D', '', raw)
        if not digits:
            return ''
        if raw.strip().startswith('+') or digits.startswith('00'):
            return digits.lstrip('0')
        country = self.country_id or self.env.company.country_id
        prefix = str(country.phone_code or '') if country else ''
        digits = digits.lstrip('0')
        if prefix == '54' and not digits.startswith('9'):
            digits = '9' + digits  # Argentina: mobile numbers need the 9 after the country code on WhatsApp
        return prefix + digits if prefix and not digits.startswith(prefix) else digits

    def _oph_whatsapp_action(self, message):
        self.ensure_one()
        number = self._oph_whatsapp_number()
        if not number:
            raise UserError(_("%s has no phone number.", self.name))
        return {'type': 'ir.actions.act_url', 'target': 'new',
                'url': 'https://wa.me/%s?text=%s' % (number, quote(message))}

    def action_oph_whatsapp_control(self):
        self.ensure_one()
        first_name = (self.name or '').split(' ')[0]
        if self.oph_next_control_date:
            message = _("Hello %(name)s! This is %(clinic)s. Your next eye control is due on %(date)s. "
                        "Reply to this message to book your appointment.", name=first_name,
                        clinic=self.env.company.name,
                        date=format_date(self.env, self.oph_next_control_date, lang_code=self.lang or self.env.lang))
        else:
            message = _("Hello %(name)s! This is %(clinic)s.", name=first_name, clinic=self.env.company.name)
        return self._oph_whatsapp_action(message)

    @api.model
    def _cron_oph_control_recall(self):
        """Weekly: email the patients whose control date is in the next 15 days or passed less than 60 days ago
        and who have no future appointment."""
        today = fields.Date.context_today(self)
        template = self.env.ref('odossey_ophthalmology.mail_template_control_recall', raise_if_not_found=False)
        if not template:
            return
        patients = self.search([
            ('is_oph_patient', '=', True), ('oph_next_control_date', '!=', False),
            ('oph_next_control_date', '<=', today + timedelta(days=15)),
            ('oph_next_control_date', '>=', today - timedelta(days=60)), ('email', '!=', False),
        ])
        now = fields.Datetime.now()
        booked = self.env['calendar.event'].search([('oph_patient_id', 'in', patients.ids), ('start', '>=', now),
                                                    ('oph_state', 'not in', ('cancelled', 'no_show'))])
        for patient in patients - booked.oph_patient_id:
            if patient.oph_recall_sent_for == patient.oph_next_control_date:
                continue
            template.send_mail(patient.id)
            patient.oph_recall_sent_for = patient.oph_next_control_date


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    def _oph_reminder_message(self):
        self.ensure_one()
        patient = self.oph_patient_id
        lang = patient.lang or self.env.lang
        tz = patient.tz or self.env.user.tz or 'America/Argentina/Buenos_Aires'
        when = format_datetime(self.env, self.start, tz=tz, dt_format='short', lang_code=lang)
        message = _("Hello %(name)s! We remind you of your appointment at %(clinic)s on %(when)s with %(doctor)s.",
                    name=(patient.name or '').split(' ')[0], clinic=self.env.company.name, when=when,
                    doctor=self.user_id.name or '')
        if self.oph_appointment_type_id.visit_type in ('first', 'control'):
            message += ' ' + _("Bring your current glasses and the list of the medication you use. Your pupils may "
                               "be dilated: come with a companion and do not drive afterwards.")
        if self.oph_insurance_id:
            message += ' ' + _("Remember to bring your health insurance card and ID.")
        return message

    @api.model
    def _cron_oph_appointment_reminders(self):
        """Daily: email tomorrow's patients (local day of the clinic)."""
        template = self.env.ref('odossey_ophthalmology.mail_template_appointment_reminder', raise_if_not_found=False)
        if not template:
            return
        tz = pytz.timezone(self.env.user.tz or 'America/Argentina/Buenos_Aires')
        tomorrow = fields.Date.context_today(self) + timedelta(days=1)
        start = tz.localize(datetime.combine(tomorrow, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        stop = start + timedelta(days=1)
        events = self.search([('oph_patient_id', '!=', False), ('start', '>=', start), ('start', '<', stop),
                              ('oph_state', 'in', ('booked', 'confirmed')), ('oph_reminder_sent', '=', False),
                              ('oph_patient_id.email', '!=', False)])
        for event in events:
            template.send_mail(event.id)
            event.oph_reminder_sent = True
