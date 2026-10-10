import hashlib
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class VetPrescription(models.Model):
    _name = 'vet.prescription'
    _description = 'Veterinary Prescription'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string="Number", readonly=True, copy=False, default=lambda self: _("New"))
    state = fields.Selection([('draft', "Draft"), ('issued', "Issued"), ('cancel', "Cancelled")],
                             default='draft', required=True, tracking=True, copy=False)
    prescription_type = fields.Selection([
        ('simple', "Simple prescription"),
        ('archived', "Archived prescription (controlled drugs)"),
    ], string="Type", default='simple', required=True, tracking=True,
        help="Archived: mandatory when a controlled drug (psychotropic / narcotic) is prescribed. "
             "Two copies are printed: the original stays at the pharmacy.")
    pet_id = fields.Many2one('vet.pet', string="Patient", required=True, tracking=True, index=True)
    owner_id = fields.Many2one(related='pet_id.owner_id', store=True, string="Owner")
    species_id = fields.Many2one(related='pet_id.species_id')
    pet_weight = fields.Float(string="Weight (kg)", digits=(16, 2))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    consultation_id = fields.Many2one('vet.consultation', string="Consultation", index=True)
    vet_id = fields.Many2one('res.users', string="Veterinarian", required=True, tracking=True,
                             default=lambda self: self.env.user if self.env.user.vet_is_veterinarian else False,
                             domain="[('vet_is_veterinarian', '=', True)]")
    vet_license = fields.Char(related='vet_id.vet_license', string="License No.")
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    validity_days = fields.Integer(string="Valid for (days)", default=30,
                                   help="Electronic veterinary prescriptions in Argentina are valid 30 or 45 days (Res. SENASA 654/2026).")
    expiry_date = fields.Date(compute='_compute_expiry_date', store=True)
    diagnosis = fields.Char()
    line_ids = fields.One2many('vet.prescription.line', 'prescription_id', string="Medications", copy=True)
    notes = fields.Text(string="Indications")
    has_controlled = fields.Boolean(compute='_compute_has_controlled', store=True)
    # Argentina: electronic veterinary prescription (RVE, Res. SENASA 654/2026)
    cuve = fields.Char(string="CUVE", tracking=True, copy=False,
                       help="Unique electronic verification code of the RVE issued in SENASA's SIGTRAZAVET (Argentina).")
    rve_state = fields.Selection([('not_required', "Not required"), ('pending', "To issue in SENASA"), ('issued', "Issued in SENASA")],
                                 string="Electronic Prescription", default='not_required', tracking=True,
                                 help="Status of the electronic prescription in the official system (SENASA SIGTRAZAVET / Italian REV).")
    content_hash = fields.Char(string="Integrity Hash", readonly=True, copy=False,
                               help="SHA-256 fingerprint of the prescription content, fixed when it is issued.")
    issued_on = fields.Datetime(readonly=True, copy=False)

    @api.depends('date', 'validity_days')
    def _compute_expiry_date(self):
        for rec in self:
            rec.expiry_date = rec.date + timedelta(days=rec.validity_days) if rec.date and rec.validity_days else False

    @api.depends('line_ids.product_id.vet_controlled')
    def _compute_has_controlled(self):
        for rec in self:
            rec.has_controlled = any(rec.line_ids.product_id.mapped('vet_controlled'))

    @api.onchange('line_ids')
    def _onchange_lines_controlled(self):
        if any(self.line_ids.product_id.mapped('vet_controlled')):
            self.prescription_type = 'archived'

    @api.onchange('pet_id')
    def _onchange_pet_id(self):
        if self.pet_id:
            self.pet_weight = self.pet_id.weight

    @api.constrains('prescription_type', 'line_ids')
    def _check_controlled(self):
        for rec in self:
            if rec.has_controlled and rec.prescription_type != 'archived':
                raise ValidationError(_("The prescription contains a controlled drug: it must be an archived prescription."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('pet_id') and not vals.get('pet_weight'):
                vals['pet_weight'] = self.env['vet.pet'].browse(vals['pet_id']).weight
            product_ids = [cmd[2].get('product_id') for cmd in vals.get('line_ids') or []
                           if isinstance(cmd, (list, tuple)) and cmd[0] == 0 and cmd[2]]
            if any(self.env['product.product'].browse([p for p in product_ids if p]).mapped('vet_controlled')):
                vals['prescription_type'] = 'archived'
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered(lambda r: r.state == 'issued') and set(vals) - {'state', 'cuve', 'rve_state', 'message_main_attachment_id', 'access_token'}:
            raise UserError(_("An issued prescription cannot be modified: cancel it and issue a new one."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda r: r.state == 'issued'):
            raise UserError(_("Issued prescriptions cannot be deleted; cancel them instead."))
        return super().unlink()

    def _compute_content_hash(self):
        self.ensure_one()
        parts = [self.name or '', str(self.date), self.pet_id.name or '', self.owner_id.name or '',
                 self.vet_id.name or '', self.vet_license or '', self.prescription_type]
        for line in self.line_ids:
            parts += [line.product_id.display_name or '', line.dose or '', line.frequency or '', str(line.duration_days),
                      str(line.quantity), line.instructions or '']
        return hashlib.sha256('|'.join(parts).encode()).hexdigest()

    def action_issue(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Add at least one medication to the prescription."))
            if not rec.vet_id.vet_license:
                raise UserError(_("The veterinarian %s has no professional license number: set it in the user preferences.", rec.vet_id.name))
            vals = {'state': 'issued', 'issued_on': fields.Datetime.now()}
            if not rec.name or rec.name == _("New"):
                code = 'vet.prescription.archived' if rec.prescription_type == 'archived' else 'vet.prescription'
                vals['name'] = self.env['ir.sequence'].next_by_code(code) or _("New")
            super(VetPrescription, rec).write(vals)
            super(VetPrescription, rec).write({'content_hash': rec._compute_content_hash()})
        return True

    def action_cancel(self):
        super(VetPrescription, self).write({'state': 'cancel'})

    def action_reset_draft(self):
        for rec in self:
            if rec.state == 'issued':
                raise UserError(_("Issued prescriptions cannot go back to draft; cancel them and create a new one."))
        self.write({'state': 'draft'})

    def action_print(self):
        return self.env.ref('odossey_veterinary.action_report_prescription').report_action(self)

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/my/vet/prescriptions/%s' % rec.id

    def _get_report_base_filename(self):
        self.ensure_one()
        return _("Prescription %s", self.name)


class VetPrescriptionLine(models.Model):
    _name = 'vet.prescription.line'
    _description = 'Prescription Line'
    _order = 'prescription_id, sequence, id'

    prescription_id = fields.Many2one('vet.prescription', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', string="Medication", required=True,
                                 domain="[('vet_kind', 'in', ('medication', 'antiparasitic', 'vaccine'))]")
    active_ingredient = fields.Char(related='product_id.vet_active_ingredient')
    presentation = fields.Char(related='product_id.vet_presentation')
    concentration = fields.Char(related='product_id.vet_concentration')
    controlled = fields.Boolean(related='product_id.vet_controlled')
    reference_dose = fields.Char(related='product_id.vet_dose')
    dose = fields.Char(required=True, help="e.g. 1 tablet, 0.5 ml, 10 mg/kg")
    frequency = fields.Char(help="e.g. every 12 h")
    duration_days = fields.Integer(string="Days")
    route = fields.Selection(related='product_id.vet_route', readonly=False, store=True)
    quantity = fields.Float(string="Qty to Dispense", default=1.0, digits='Product Unit')
    instructions = fields.Char()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and not self.dose and self.product_id.vet_dose:
            self.instructions = self.product_id.vet_dose


class VetPet(models.Model):
    _inherit = 'vet.pet'

    prescription_ids = fields.One2many('vet.prescription', 'pet_id', string="Prescriptions")
    prescription_count = fields.Integer(compute='_compute_prescription_count')

    def _compute_prescription_count(self):
        for pet in self:
            pet.prescription_count = len(pet.prescription_ids)

    def action_view_prescriptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vet.prescription', 'view_mode': 'list,form',
            'name': _("Prescriptions"), 'domain': [('pet_id', '=', self.id)], 'context': {'default_pet_id': self.id},
        }
