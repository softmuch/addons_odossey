from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

PREVENTIVE_STATES = [
    ('done', "Replaced"),
    ('up_to_date', "Up to date"),
    ('due_soon', "Due soon"),
    ('overdue', "Overdue"),
    ('no_booster', "No booster"),
]


def _due_soon_days(env):
    return int(env['ir.config_parameter'].sudo().get_param('odossey_veterinary.due_soon_days', 30))


class VetVaccination(models.Model):
    _name = 'vet.vaccination'
    _description = 'Vaccination / Parasite Control'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _rec_name = 'product_id'

    pet_id = fields.Many2one('vet.pet', string="Patient", required=True, ondelete='cascade', index=True)
    owner_id = fields.Many2one(related='pet_id.owner_id', store=True, string="Owner")
    species_id = fields.Many2one(related='pet_id.species_id', store=True)
    company_id = fields.Many2one(related='pet_id.company_id', store=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    preventive_type = fields.Selection([
        ('vaccine', "Vaccine"), ('internal', "Internal deworming"), ('external', "External antiparasitic"),
    ], string="Type", required=True, default='vaccine')
    product_id = fields.Many2one('product.product', string="Product", required=True,
                                 domain="[('vet_kind', 'in', ('vaccine', 'antiparasitic'))]")
    preventive_group = fields.Selection(related='product_id.vet_preventive_group', store=True, string="Group")
    dose_number = fields.Integer(string="Dose No.", default=0,
                                 help="Dose number within the group; filled in automatically from the previous doses.")
    lot_id = fields.Many2one('stock.lot', string="Lot", domain="[('product_id', '=', product_id)]")
    lot_name = fields.Char(string="Lot / Serial", help="Batch number printed on the vaccine label.")
    expiration_date = fields.Date(string="Lot Expiry")
    vet_id = fields.Many2one('res.users', string="Veterinarian", default=lambda self: self.env.user,
                             domain="[('vet_is_veterinarian', '=', True)]")
    consultation_id = fields.Many2one('vet.consultation', string="Consultation", ondelete='set null', index=True)
    next_date = fields.Date(string="Next Due", compute='_compute_next_date', store=True, readonly=False, tracking=True,
                            help="Computed from the product schedule (primary course / booster / repeat interval); can be changed.")
    superseded = fields.Boolean(string="Replaced", readonly=True,
                                help="A later dose of the same group has been applied.")
    state = fields.Selection(PREVENTIVE_STATES, compute='_compute_state', search='_search_state')
    reminder_date = fields.Date(string="Reminder Sent On", readonly=True, copy=False)
    note = fields.Char()

    # ------------------------------------------------------------------ computes
    @api.depends('date', 'product_id', 'dose_number')
    def _compute_next_date(self):
        for rec in self:
            tmpl = rec.product_id.product_tmpl_id
            if not rec.date or not tmpl:
                rec.next_date = False
            elif rec.preventive_type != 'vaccine' or tmpl.vet_kind == 'antiparasitic':
                rec.next_date = rec.date + timedelta(days=tmpl.vet_repeat_days) if tmpl.vet_repeat_days else False
            elif rec.dose_number and rec.dose_number < (tmpl.vet_initial_doses or 1) and tmpl.vet_dose_interval_weeks:
                rec.next_date = rec.date + timedelta(weeks=tmpl.vet_dose_interval_weeks)
            elif tmpl.vet_booster_months:
                rec.next_date = rec.date + relativedelta(months=tmpl.vet_booster_months)
            else:
                rec.next_date = False

    @api.depends('next_date', 'superseded')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=_due_soon_days(self.env))
        for rec in self:
            if rec.superseded:
                rec.state = 'done'
            elif not rec.next_date:
                rec.state = 'no_booster'
            elif rec.next_date < today:
                rec.state = 'overdue'
            elif rec.next_date <= soon:
                rec.state = 'due_soon'
            else:
                rec.state = 'up_to_date'

    def _search_state(self, operator, value):
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=_due_soon_days(self.env))
        domains = {
            'done': [('superseded', '=', True)],
            'no_booster': [('superseded', '=', False), ('next_date', '=', False)],
            'overdue': [('superseded', '=', False), ('next_date', '<', today)],
            'due_soon': [('superseded', '=', False), ('next_date', '>=', today), ('next_date', '<=', soon)],
            'up_to_date': [('superseded', '=', False), ('next_date', '>', soon)],
        }
        values = [value] if isinstance(value, (str, bool)) or value is None else list(value)
        ids = set()
        for val in values:
            ids |= set(self.search(domains.get(val, [('id', '=', 0)])).ids)
        positive = operator in ('=', 'in')
        return [('id', 'in' if positive else 'not in', list(ids))]

    # ------------------------------------------------------------------ onchanges
    @api.onchange('product_id')
    def _onchange_product_id(self):
        tmpl = self.product_id.product_tmpl_id
        if tmpl.vet_kind == 'antiparasitic':
            self.preventive_type = 'external' if tmpl.vet_preventive_group == 'external_parasites' else 'internal'
        elif tmpl.vet_kind == 'vaccine':
            self.preventive_type = 'vaccine'

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        if self.lot_id:
            self.lot_name = self.lot_id.name
            self.expiration_date = getattr(self.lot_id, 'expiration_date', False) and self.lot_id.expiration_date.date()

    # ------------------------------------------------------------------ constraints
    @api.constrains('date', 'expiration_date', 'pet_id')
    def _check_dates(self):
        for rec in self:
            if rec.expiration_date and rec.date and rec.expiration_date < rec.date:
                raise ValidationError(_("The lot %(lot)s of %(product)s expired before the application date.",
                                        lot=rec.lot_name or '', product=rec.product_id.display_name))
            if rec.pet_id.birthdate and rec.date and rec.date < rec.pet_id.birthdate:
                raise ValidationError(_("The application date is before the date of birth of %s.", rec.pet_id.name))

    # ------------------------------------------------------------------ CRUD
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            product = self.env['product.product'].browse(vals.get('product_id'))
            tmpl = product.product_tmpl_id
            if 'preventive_type' not in vals and tmpl.vet_kind == 'antiparasitic':
                vals['preventive_type'] = 'external' if tmpl.vet_preventive_group == 'external_parasites' else 'internal'
            if vals.get('lot_id') and not vals.get('lot_name'):
                lot = self.env['stock.lot'].browse(vals['lot_id'])
                vals['lot_name'] = lot.name
                if not vals.get('expiration_date') and getattr(lot, 'expiration_date', False):
                    vals['expiration_date'] = lot.expiration_date.date()
            if not vals.get('dose_number') and vals.get('pet_id'):
                vals['dose_number'] = self._vet_next_dose_number(vals['pet_id'], product, vals.get('date'))
        records = super().create(vals_list)
        records.pet_id._vet_refresh_preventive()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'date', 'product_id', 'pet_id'} & set(vals):
            self.pet_id._vet_refresh_preventive()
        return res

    def unlink(self):
        pets = self.pet_id
        res = super().unlink()
        pets.exists()._vet_refresh_preventive()
        return res

    def _vet_next_dose_number(self, pet_id, product, date=None):
        tmpl = product.product_tmpl_id
        group = tmpl.vet_preventive_group
        domain = [('pet_id', '=', pet_id)]
        domain += [('preventive_group', '=', group)] if group else [('product_id', '=', product.id)]
        if date:
            domain.append(('date', '<=', date))
        previous = self.search(domain, order='date desc, id desc', limit=1)
        return previous.dose_number + 1 if previous else 1

    def action_print_rabies_certificate(self):
        return self.env.ref('odossey_veterinary.action_report_rabies_certificate').report_action(self)


class VetPet(models.Model):
    _inherit = 'vet.pet'

    vaccination_ids = fields.One2many('vet.vaccination', 'pet_id', string="Preventive Care")
    vaccination_count = fields.Integer(compute='_compute_vaccination_info')
    vaccination_state = fields.Selection([
        ('none', "No record"), ('up_to_date', "Up to date"), ('due_soon', "Due soon"), ('overdue', "Overdue"),
    ], string="Vaccination Status", compute='_compute_vaccination_info', search='_search_vaccination_state')
    next_preventive_date = fields.Date(string="Next Due Date", compute='_compute_vaccination_info')

    @api.depends('vaccination_ids.next_date', 'vaccination_ids.superseded')
    def _compute_vaccination_info(self):
        for pet in self:
            active = pet.vaccination_ids.filtered(lambda v: not v.superseded and v.next_date)
            pet.vaccination_count = len(pet.vaccination_ids)
            pet.next_preventive_date = min(active.mapped('next_date')) if active else False
            states = set(active.mapped('state'))
            if pet.deceased or not pet.vaccination_ids:
                pet.vaccination_state = 'none'
            elif 'overdue' in states:
                pet.vaccination_state = 'overdue'
            elif 'due_soon' in states:
                pet.vaccination_state = 'due_soon'
            else:
                pet.vaccination_state = 'up_to_date'

    def _search_vaccination_state(self, operator, value):
        values = [value] if isinstance(value, (str, bool)) or value is None else list(value)
        Vacc = self.env['vet.vaccination']
        ids = set()
        for val in values:
            if val in ('overdue', 'due_soon', 'up_to_date'):
                pets = Vacc.search([('state', '=', val), ('pet_id.deceased', '=', False)]).pet_id
                if val == 'due_soon':
                    pets -= Vacc.search([('state', '=', 'overdue')]).pet_id
                elif val == 'up_to_date':
                    pets = self.search([('vaccination_ids', '!=', False), ('deceased', '=', False)])
                    pets -= Vacc.search([('state', 'in', ('overdue', 'due_soon'))]).pet_id
                ids |= set(pets.ids)
            elif val == 'none':
                ids |= set(self.search(['|', ('vaccination_ids', '=', False), ('deceased', '=', True)]).ids)
        positive = operator in ('=', 'in')
        return [('id', 'in' if positive else 'not in', list(ids))]

    def _vet_refresh_preventive(self):
        """Only the latest dose of each group stays 'active' in the plan."""
        for pet in self:
            seen = set()
            for rec in pet.vaccination_ids.sorted(lambda v: (v.date, v.id), reverse=True):
                key = rec.preventive_group or ('product', rec.product_id.id)
                superseded = key in seen
                seen.add(key)
                if rec.superseded != superseded:
                    rec.with_context(tracking_disable=True).superseded = superseded

    def action_view_vaccinations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Preventive Care"),
            'res_model': 'vet.vaccination',
            'view_mode': 'list,form',
            'domain': [('pet_id', '=', self.id)],
            'context': {'default_pet_id': self.id},
        }

    def action_print_vaccination_card(self):
        return self.env.ref('odossey_veterinary.action_report_vaccination_card').report_action(self)

    def _get_report_base_filename(self):
        self.ensure_one()
        return _("Vaccination card %s", self.name)
