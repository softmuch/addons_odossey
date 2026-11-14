import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _digits(phone):
    return re.sub(r'\D', '', phone or '')


class VetAppointmentRegister(models.TransientModel):
    _name = 'vet.appointment.register'
    _description = 'Register the patient of a phone booking'

    appointment_id = fields.Many2one('calendar.event', required=True, ondelete='cascade')
    owner_id = fields.Many2one('res.partner', string="Existing Owner",
                               help="Pick the owner if already registered (found by phone automatically); "
                                    "leave empty to create a new one with the data below.")
    owner_name = fields.Char(string="Owner Name")
    owner_phone = fields.Char(string="Phone")
    owner_email = fields.Char(string="Email")
    owner_vat = fields.Char(string="ID / Tax Number", help="DNI or CUIT, for the invoice. Can be added later.")
    pet_id = fields.Many2one('vet.pet', string="Existing Patient", domain="[('owner_id', '=', owner_id)]",
                             help="Pick the patient if the owner already has it registered.")
    pet_name = fields.Char(string="Patient Name")
    species_id = fields.Many2one('vet.species', string="Species")
    breed_id = fields.Many2one('vet.breed', string="Breed", domain="[('species_id', '=', species_id)]")
    sex = fields.Selection([('male', "Male"), ('female', "Female"), ('unknown', "Unknown")], default='unknown')
    birthdate = fields.Date(string="Birthdate")
    phone_match_ids = fields.Many2many('res.partner', compute='_compute_phone_match_ids', string="Same Phone")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        event = self.env['calendar.event'].browse(res.get('appointment_id') or self.env.context.get('default_appointment_id'))
        if event:
            res.update({
                'owner_name': event.vet_contact_name, 'owner_phone': event.vet_contact_phone,
                'pet_name': event.vet_contact_pet_name, 'species_id': event.vet_contact_species_id.id,
            })
            matches = self._find_owners(event.vet_contact_phone)
            if len(matches) == 1:
                res['owner_id'] = matches.id
        return res

    @api.model
    def _find_owners(self, phone):
        digits = _digits(phone)
        if len(digits) < 6:
            return self.env['res.partner']
        candidates = self.env['res.partner'].search([('phone', 'ilike', digits[-4:])], limit=50)
        return candidates.filtered(lambda p: _digits(p.phone)[-8:] == digits[-8:])

    @api.depends('owner_phone')
    def _compute_phone_match_ids(self):
        for wizard in self:
            wizard.phone_match_ids = wizard._find_owners(wizard.owner_phone)

    @api.onchange('owner_id')
    def _onchange_owner_id(self):
        if self.pet_id and self.pet_id.owner_id != self.owner_id:
            self.pet_id = False
        if self.owner_id and self.pet_name:
            same = self.owner_id.vet_pet_ids.filtered(lambda p: p.name.strip().lower() == self.pet_name.strip().lower())
            if len(same) == 1:
                self.pet_id = same

    @api.onchange('species_id')
    def _onchange_species_id(self):
        if self.breed_id.species_id != self.species_id:
            self.breed_id = False

    def action_confirm(self):
        self.ensure_one()
        owner = self.owner_id
        if not owner:
            if not self.owner_name:
                raise UserError(_("Write the name of the owner or pick an existing one."))
            owner = self.env['res.partner'].create({
                'name': self.owner_name, 'phone': self.owner_phone or False, 'email': self.owner_email or False,
                'vat': self.owner_vat or False,
            })
        else:
            vals = {}
            if self.owner_phone and not owner.phone:
                vals['phone'] = self.owner_phone
            if self.owner_email and not owner.email:
                vals['email'] = self.owner_email
            if vals:
                owner.write(vals)
        pet = self.pet_id
        if not pet:
            if not self.pet_name or not self.species_id:
                raise UserError(_("Write the name and the species of the patient or pick an existing one."))
            pet = self.env['vet.pet'].create({
                'name': self.pet_name, 'owner_id': owner.id, 'species_id': self.species_id.id,
                'breed_id': self.breed_id.id, 'sex': self.sex or 'unknown', 'birthdate': self.birthdate,
            })
        event = self.appointment_id
        event.write({'vet_pet_id': pet.id, 'partner_ids': [(4, owner.id)],
                     'name': event._vet_title(pet.name, False, event.vet_appointment_type_id)})
        if self.env.context.get('vet_start_consultation'):
            return event.action_vet_start_consultation()
        return {'type': 'ir.actions.act_window_close'}
