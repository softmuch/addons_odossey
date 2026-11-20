from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResourceCalendarAttendance(models.Model):
    _inherit = 'resource.calendar.attendance'

    vet_slot_minutes = fields.Integer(
        string="Agenda Slot (min)", default=0,
        help="Length of the rows of the veterinary agenda on this day; 0 uses the general slot of the settings. "
             "Every period of the same day must use the same value. Example: 20 minutes from Monday to Friday and "
             "30 on Saturday → leave 0 on weekdays (general slot 20) and type 30 in the Saturday rows.")

    @api.constrains('vet_slot_minutes', 'dayofweek', 'calendar_id', 'week_type')
    def _check_vet_slot_minutes(self):
        for att in self:
            if att.vet_slot_minutes and not 5 <= att.vet_slot_minutes <= 120:
                raise ValidationError(_("The agenda slot must be 0 (general slot) or between 5 and 120 minutes."))
            if not att.vet_slot_minutes or att.display_type:
                continue
            others = att.calendar_id.attendance_ids.filtered(
                lambda a: a != att and not a.display_type and a.dayofweek == att.dayofweek
                and a.week_type == att.week_type and a.vet_slot_minutes and a.vet_slot_minutes != att.vet_slot_minutes)
            if others:
                raise ValidationError(_(
                    "All the periods of the same day must use the same agenda slot (%(day)s: %(a)s and %(b)s minutes).",
                    day=dict(att._fields['dayofweek']._description_selection(self.env)).get(att.dayofweek),
                    a=att.vet_slot_minutes, b=others[0].vet_slot_minutes))
