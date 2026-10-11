import re
from collections import defaultdict
from datetime import timedelta
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date


class VetPet(models.Model):
    _inherit = 'vet.pet'

    def _vet_due_preventive(self, days=None):
        """Active (not replaced) preventive records due within `days` days or already overdue."""
        if days is None:
            days = int(self.env['ir.config_parameter'].sudo().get_param('odossey_veterinary.reminder_days', 7))
        limit = fields.Date.context_today(self) + timedelta(days=days)
        return self.env['vet.vaccination'].search([
            ('pet_id', 'in', self.ids), ('superseded', '=', False), ('next_date', '!=', False),
            ('next_date', '<=', limit), ('pet_id.deceased', '=', False), ('pet_id.active', '=', True),
        ], order='next_date')

    def action_whatsapp_owner(self):
        self.ensure_one()
        return self.owner_id._vet_whatsapp_action(self._vet_whatsapp_message())

    def _vet_whatsapp_message(self):
        self.ensure_one()
        due = self._vet_due_preventive(days=60)
        owner_name = (self.owner_id.name or '').split(' ')[0]
        if due:
            items = '\n'.join('• %s: %s (%s)' % (rec.pet_id.name, rec.product_id.name, format_date(self.env, rec.next_date, lang_code=self.owner_id.lang or self.env.lang))
                              for rec in due)
            return _("Hello %(owner)s! This is %(clinic)s. These preventive treatments are due:\n%(items)s\n"
                     "Reply to this message to book an appointment.",
                     owner=owner_name, clinic=self.env.company.name, items=items)
        return _("Hello %(owner)s! This is %(clinic)s, about %(pet)s.", owner=owner_name,
                 clinic=self.env.company.name, pet=self.name)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _vet_whatsapp_number(self):
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

    def _vet_whatsapp_action(self, message):
        self.ensure_one()
        number = self._vet_whatsapp_number()
        if not number:
            raise UserError(_("%s has no phone number.", self.name))
        return {'type': 'ir.actions.act_url', 'target': 'new',
                'url': 'https://wa.me/%s?text=%s' % (number, quote(message))}


class VetVaccination(models.Model):
    _inherit = 'vet.vaccination'

    @api.model
    def _cron_send_reminders(self):
        """Daily: one email per owner listing every pet's preventive care that is due soon or overdue."""
        days = int(self.env['ir.config_parameter'].sudo().get_param('odossey_veterinary.reminder_days', 7))
        limit = fields.Date.context_today(self) + timedelta(days=days)
        records = self.search([
            ('superseded', '=', False), ('next_date', '!=', False), ('next_date', '<=', limit),
            ('reminder_date', '=', False), ('pet_id.deceased', '=', False), ('pet_id.active', '=', True),
            ('owner_id.email', '!=', False),
        ])
        by_owner = defaultdict(lambda: self.browse())
        for rec in records:
            by_owner[rec.owner_id] |= rec
        template = self.env.ref('odossey_veterinary.mail_template_preventive_reminder', raise_if_not_found=False)
        today = fields.Date.context_today(self)
        for owner, recs in by_owner.items():
            if template:
                template.with_context(vet_reminder_records=recs).send_mail(owner.id, force_send=False)
            recs.write({'reminder_date': today})
            for pet in recs.pet_id:
                pet.message_post(body=_("Reminder sent to %(owner)s: %(items)s", owner=owner.name,
                                        items=', '.join(recs.filtered(lambda r: r.pet_id == pet).mapped('product_id.name'))))
        return len(by_owner)

    def action_whatsapp_reminder(self):
        self.ensure_one()
        return self.pet_id.action_whatsapp_owner()
