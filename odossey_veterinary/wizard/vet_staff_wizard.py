import re
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class VetStaffWizard(models.TransientModel):
    """Veterinarians of the clinic, managed by the clinic administrator without the user administration rights:
    only the veterinary fields of the users are written, and new veterinarians get a user without password."""
    _name = 'vet.staff.wizard'
    _description = 'Veterinarians of the Clinic'

    line_ids = fields.One2many('vet.staff.wizard.line', 'wizard_id', string="Staff")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        users = self.env['res.users'].sudo().search([('share', '=', False)], order='name')
        res['line_ids'] = [(0, 0, {
            'user_id': user.id, 'name': user.name, 'is_veterinarian': user.vet_is_veterinarian,
            'license': user.vet_license, 'color': user.vet_color,
        }) for user in users if user != self.env.ref('base.user_root')]
        return res

    def _vet_check_manager(self):
        if not self.env.user.has_group('odossey_veterinary.group_vet_manager'):
            raise AccessError(_("Only the clinic administrator can manage the veterinarians."))

    @api.model
    def _vet_new_user_groups(self):
        """Groups of a veterinarian created from this screen (extended by the clinic modules)."""
        return self.env.ref('base.group_user') | self.env.ref('odossey_veterinary.group_vet_veterinarian')

    @api.model
    def _vet_login(self, name):
        base = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
        base = re.sub(r'^(dra?|dr\.?a?)\.?\s+', '', base)
        base = re.sub(r'[^a-z0-9]+', '.', base).strip('.') or 'vet'
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        login, count = base, 1
        while Users.search_count([('login', '=', login)]):
            count += 1
            login = '%s%s' % (base, count)
        return login

    def action_apply(self):
        self.ensure_one()
        self._vet_check_manager()
        Users = self.env['res.users'].sudo()
        for line in self.line_ids:
            vals = {'vet_is_veterinarian': line.is_veterinarian, 'vet_license': line.license or False,
                    'vet_color': line.color}
            if line.user_id:
                user = line.user_id.sudo()
                changed = {k: v for k, v in vals.items() if user[k] != v}
                if changed:
                    user.write(changed)
            elif line.name:
                if not line.is_veterinarian:
                    continue
                Users.with_context(no_reset_password=True).create(dict(
                    vals, name=line.name, login=line.login or self._vet_login(line.name),
                    group_ids=[(6, 0, self._vet_new_user_groups().ids)],
                    tz=self.env.company.resource_calendar_id.tz or self.env.user.tz,
                    lang=self.env.user.lang,
                ))
            elif line.is_veterinarian:
                raise UserError(_("Write the name of the new veterinarian."))
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'success', 'sticky': False,
                       'message': _("Veterinarians saved: they can be chosen in the agenda now."),
                       'next': {'type': 'ir.actions.act_window_close'}},
        }


class VetStaffWizardLine(models.TransientModel):
    _name = 'vet.staff.wizard.line'
    _description = 'Veterinarian of the Clinic'

    wizard_id = fields.Many2one('vet.staff.wizard', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string="User", readonly=True)
    name = fields.Char(string="Name", help="Name shown in the agenda. Example: Dra. Valentina Capiello.")
    login = fields.Char(string="Login", help="Only for new veterinarians; generated from the name when empty.")
    is_veterinarian = fields.Boolean(string="Attends Appointments", default=True,
                                     help="Listed as veterinarian in the agenda, consultations and prescriptions.")
    license = fields.Char(string="License No.")
    color = fields.Integer(string="Color")
