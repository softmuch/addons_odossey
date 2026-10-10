from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

CONSULTATION_TYPES = [
    ('consultation', "Consultation"),
    ('control', "Follow-up"),
    ('emergency', "Emergency"),
    ('vaccination', "Vaccination / Preventive"),
    ('surgery', "Surgery"),
    ('home_visit', "Home visit"),
    ('telemedicine', "Telemedicine"),
]


class VetConsultationTemplate(models.Model):
    _name = 'vet.consultation.template'
    _description = 'Consultation Template'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    consultation_type = fields.Selection(CONSULTATION_TYPES, default='consultation', required=True)
    reason = fields.Char(translate=True)
    anamnesis = fields.Html(translate=True, help="Pre-filled history questions.")
    physical_exam = fields.Html(translate=True, help="Pre-filled physical exam checklist.")
    plan = fields.Html(translate=True)
    line_ids = fields.One2many('vet.consultation.template.line', 'template_id', string="Default Charges")
    active = fields.Boolean(default=True)


class VetConsultationTemplateLine(models.Model):
    _name = 'vet.consultation.template.line'
    _description = 'Consultation Template Charge'

    template_id = fields.Many2one('vet.consultation.template', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float(default=1.0, digits='Product Unit')


class VetConsultation(models.Model):
    _name = 'vet.consultation'
    _description = 'Consultation (Medical Record)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string="Reference", readonly=True, copy=False, default=lambda self: _("New"))
    state = fields.Selection([
        ('draft', "Scheduled"), ('in_progress', "In Progress"), ('done', "Closed"), ('cancel', "Cancelled"),
    ], default='draft', required=True, tracking=True, copy=False)
    pet_id = fields.Many2one('vet.pet', string="Patient", required=True, tracking=True, index=True,
                             domain="[('deceased', '=', False)]")
    owner_id = fields.Many2one(related='pet_id.owner_id', store=True, string="Owner")
    species_id = fields.Many2one(related='pet_id.species_id', store=True)
    pet_alert_summary = fields.Char(related='pet_id.alert_summary')
    pet_has_danger_alert = fields.Boolean(related='pet_id.has_danger_alert')
    pet_allergy_notes = fields.Text(related='pet_id.allergy_notes')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    date = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True)
    vet_id = fields.Many2one('res.users', string="Veterinarian", required=True, tracking=True,
                             default=lambda self: self.env.user if self.env.user.vet_is_veterinarian else False,
                             domain="[('vet_is_veterinarian', '=', True)]")
    consultation_type = fields.Selection(CONSULTATION_TYPES, string="Type", default='consultation', required=True)
    template_id = fields.Many2one('vet.consultation.template', string="Template")
    appointment_id = fields.Many2one('calendar.event', string="Appointment", copy=False)
    reason = fields.Char(string="Reason for Visit", tracking=True)

    # S - subjective
    anamnesis = fields.Html(string="History (Anamnesis)", help="What the owner reports: symptoms, since when, appetite, "
                                                                 "vomiting/diarrhoea, medication received...")
    # O - objective: vital signs
    weight = fields.Float(string="Weight (kg)", digits=(16, 2))
    body_condition = fields.Selection([(str(i), str(i)) for i in range(1, 10)], string="Body Condition (1-9)")
    temperature = fields.Float(string="Temperature (°C)", digits=(4, 1))
    heart_rate = fields.Integer(string="Heart Rate (bpm)")
    respiratory_rate = fields.Integer(string="Respiratory Rate (rpm)")
    mucous_membranes = fields.Selection([
        ('pink', "Pink"), ('pale', "Pale"), ('cyanotic', "Cyanotic"), ('icteric', "Icteric"),
        ('congested', "Congested"), ('dry', "Dry / tacky"),
    ])
    crt = fields.Float(string="Capillary Refill Time (s)", digits=(3, 1))
    hydration = fields.Selection([
        ('normal', "Normal"), ('mild', "Mild dehydration (5-6 %)"), ('moderate', "Moderate (7-9 %)"), ('severe', "Severe (≥ 10 %)"),
    ])
    attitude = fields.Selection([
        ('bar', "Bright, alert, responsive"), ('qar', "Quiet, alert, responsive"), ('depressed', "Depressed"),
        ('stuporous', "Stuporous"), ('comatose', "Comatose"),
    ], string="Mental Status")
    pain_score = fields.Selection([('0', "0 - No pain"), ('1', "1 - Mild"), ('2', "2 - Moderate"), ('3', "3 - Severe"),
                                   ('4', "4 - Worst possible")], string="Pain Score")
    vitals_warning = fields.Char(compute='_compute_vitals_warning')
    physical_exam = fields.Html(string="Physical Examination")
    # A - assessment
    diagnosis_ids = fields.Many2many('vet.disease', string="Diagnoses")
    diagnosis_type = fields.Selection([('presumptive', "Presumptive"), ('definitive', "Definitive")], default='presumptive')
    assessment = fields.Html(string="Assessment")
    notifiable_warning = fields.Char(compute='_compute_notifiable_warning')
    # P - plan
    plan = fields.Html(string="Plan / Treatment")
    follow_up_date = fields.Date(string="Follow-up Date",
                                 help="A follow-up reminder activity is created for the reception when the consultation is closed.")
    owner_instructions = fields.Html(string="Instructions for the Owner")

    line_ids = fields.One2many('vet.consultation.line', 'consultation_id', string="Charges & Products Used", copy=True)
    amount_total = fields.Monetary(compute='_compute_amount_total', string="Total")
    currency_id = fields.Many2one(related='company_id.currency_id')
    sale_order_id = fields.Many2one('sale.order', string="Sale Order", copy=False, readonly=True)
    invoice_status = fields.Selection(related='sale_order_id.invoice_status')
    vaccination_ids = fields.One2many('vet.vaccination', 'consultation_id', string="Preventive Care Applied")
    prescription_ids = fields.One2many('vet.prescription', 'consultation_id', string="Prescriptions")
    prescription_count = fields.Integer(compute='_compute_counts')
    lab_result_ids = fields.One2many('vet.lab.result', 'consultation_id', string="Lab Results")
    consent_ids = fields.One2many('vet.consent', 'consultation_id', string="Consents")
    consent_count = fields.Integer(compute='_compute_counts')
    attachment_count = fields.Integer(compute='_compute_counts', string="Files")

    # ------------------------------------------------------------------ computes
    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('price_subtotal'))

    def _compute_counts(self):
        att = dict(self.env['ir.attachment']._read_group(
            [('res_model', '=', self._name), ('res_id', 'in', self.ids)], ['res_id'], ['__count']))
        for rec in self:
            rec.prescription_count = len(rec.prescription_ids)
            rec.consent_count = len(rec.consent_ids)
            rec.attachment_count = att.get(rec.id, 0)

    @api.depends('temperature', 'heart_rate', 'respiratory_rate', 'species_id', 'crt', 'mucous_membranes')
    def _compute_vitals_warning(self):
        ranges = {  # adult reference ranges (temperature °C, heart rate, respiratory rate)
            'DOG': ((37.5, 39.2), (60, 140), (10, 30)),
            'CAT': ((38.0, 39.2), (140, 220), (20, 30)),
        }
        for rec in self:
            warnings = []
            ref = ranges.get(rec.species_id.code or '')
            if ref:
                (t_lo, t_hi), (h_lo, h_hi), (r_lo, r_hi) = ref
                if rec.temperature and not t_lo <= rec.temperature <= t_hi:
                    warnings.append(_("Temperature %(v)s °C (ref. %(lo)s-%(hi)s)", v=rec.temperature, lo=t_lo, hi=t_hi))
                if rec.heart_rate and not h_lo <= rec.heart_rate <= h_hi:
                    warnings.append(_("Heart rate %(v)s bpm (ref. %(lo)s-%(hi)s)", v=rec.heart_rate, lo=h_lo, hi=h_hi))
                if rec.respiratory_rate and not r_lo <= rec.respiratory_rate <= r_hi:
                    warnings.append(_("Respiratory rate %(v)s rpm (ref. %(lo)s-%(hi)s)", v=rec.respiratory_rate, lo=r_lo, hi=r_hi))
            if rec.crt and rec.crt > 2:
                warnings.append(_("Capillary refill time %s s (> 2 s)", rec.crt))
            if rec.mucous_membranes in ('pale', 'cyanotic', 'icteric'):
                warnings.append(dict(self._fields['mucous_membranes']._description_selection(self.env))[rec.mucous_membranes])
            rec.vitals_warning = ' · '.join(warnings)

    @api.depends('diagnosis_ids.notifiable', 'diagnosis_ids.zoonosis')
    def _compute_notifiable_warning(self):
        for rec in self:
            parts = []
            notifiable = rec.diagnosis_ids.filtered('notifiable')
            zoonosis = rec.diagnosis_ids.filtered('zoonosis')
            if notifiable:
                parts.append(_("Notifiable disease (report to the health authority): %s", ', '.join(notifiable.mapped('name'))))
            if zoonosis:
                parts.append(_("Zoonosis - inform the owner about precautions: %s", ', '.join(zoonosis.mapped('name'))))
            rec.notifiable_warning = ' · '.join(parts)

    # ------------------------------------------------------------------ onchanges
    @api.onchange('pet_id')
    def _onchange_pet_id(self):
        if self.pet_id and not self.weight:
            self.weight = self.pet_id.weight

    @api.onchange('template_id')
    def _onchange_template_id(self):
        tmpl = self.template_id
        if not tmpl:
            return
        self.consultation_type = tmpl.consultation_type
        self.reason = self.reason or tmpl.reason
        if tmpl.anamnesis:
            self.anamnesis = tmpl.anamnesis
        if tmpl.physical_exam:
            self.physical_exam = tmpl.physical_exam
        if tmpl.plan:
            self.plan = tmpl.plan
        existing = self.line_ids.product_id
        for tline in tmpl.line_ids.filtered(lambda tl: tl.product_id not in existing):
            self.line_ids = [(0, 0, {'product_id': tline.product_id.id, 'quantity': tline.quantity,
                                     'price_unit': tline.product_id.lst_price, 'name': tline.product_id.display_name})]

    # ------------------------------------------------------------------ CRUD
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('vet.consultation') or _("New")
        return super().create(vals_list)

    def write(self, vals):
        locked = {'pet_id', 'anamnesis', 'physical_exam', 'assessment', 'diagnosis_ids', 'temperature', 'heart_rate',
                  'respiratory_rate', 'weight', 'plan'}
        if locked & set(vals) and not self.env.context.get('vet_allow_closed_edit'):
            closed = self.filtered(lambda c: c.state == 'done')
            if closed:
                raise UserError(_("The consultation %s is closed: the medical record can no longer be modified. "
                                  "Add a new follow-up consultation instead.", ', '.join(closed.mapped('name'))))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda c: c.state == 'done'):
            raise UserError(_("Closed consultations are part of the medical record and cannot be deleted."))
        return super().unlink()

    # ------------------------------------------------------------------ actions
    def action_start(self):
        self.write({'state': 'in_progress'})
        for rec in self.filtered('appointment_id'):
            rec.appointment_id.vet_state = 'in_consultation'

    def action_done(self):
        for rec in self:
            if not rec.vet_id:
                raise UserError(_("Select the veterinarian before closing the consultation."))
            if rec.weight and (not rec.pet_id.weight or abs(rec.pet_id.weight - rec.weight) > 0.001
                               or rec.pet_id.weight_date != fields.Date.context_today(rec)):
                self.env['vet.weight'].create({
                    'pet_id': rec.pet_id.id, 'weight': rec.weight, 'body_condition': rec.body_condition,
                    'date': fields.Date.context_today(rec), 'note': rec.name,
                })
            rec.line_ids._vet_create_preventive_records()
            if rec.follow_up_date:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo', date_deadline=rec.follow_up_date,
                    summary=_("Follow-up of %s", rec.pet_id.name),
                    note=_("Contact %(owner)s to book the follow-up of %(pet)s.", owner=rec.owner_id.name, pet=rec.pet_id.name),
                    user_id=rec.vet_id.id or self.env.user.id)
            if rec.appointment_id:
                rec.appointment_id.vet_state = 'done'
        self.write({'state': 'done'})
        if self.env['ir.config_parameter'].sudo().get_param('odossey_veterinary.auto_sale_order', 'True') == 'True':
            self.filtered(lambda c: c.line_ids and not c.sale_order_id).action_create_sale_order()

    def action_cancel(self):
        if self.filtered(lambda c: c.sale_order_id and c.sale_order_id.state == 'sale'):
            raise UserError(_("Cancel the confirmed sale order first."))
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        self.with_context(vet_allow_closed_edit=True).write({'state': 'in_progress'})

    def action_create_sale_order(self):
        SaleOrder = self.env['sale.order']
        for rec in self:
            if rec.sale_order_id:
                continue
            lines = rec.line_ids.filtered(lambda l: l.product_id and not l.sale_line_id)
            if not lines:
                raise UserError(_("Add at least one charge to the consultation %s.", rec.name))
            order = SaleOrder.create({
                'partner_id': rec.owner_id.id,
                'company_id': rec.company_id.id,
                'origin': rec.name,
                'vet_consultation_id': rec.id,
                'vet_pet_id': rec.pet_id.id,
                'order_line': [(0, 0, line._vet_sale_line_vals()) for line in lines],
            })
            for line, sol in zip(lines, order.order_line):
                line.sale_line_id = sol
            rec.sale_order_id = order
            rec.message_post(body=_("Sale order %s created.", order._get_html_link()))
        return self.action_view_sale_order() if len(self) == 1 else True

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'sale.order', 'res_id': self.sale_order_id.id,
            'view_mode': 'form', 'name': self.sale_order_id.name,
        }

    def action_new_prescription(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vet.prescription', 'view_mode': 'form',
            'name': _("New Prescription"),
            'context': {'default_pet_id': self.pet_id.id, 'default_consultation_id': self.id,
                        'default_vet_id': self.vet_id.id},
        }

    def action_view_prescriptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vet.prescription', 'view_mode': 'list,form',
            'name': _("Prescriptions"), 'domain': [('consultation_id', '=', self.id)],
            'context': {'default_pet_id': self.pet_id.id, 'default_consultation_id': self.id, 'default_vet_id': self.vet_id.id},
        }

    def action_view_consents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vet.consent', 'view_mode': 'list,form',
            'name': _("Consents"), 'domain': [('consultation_id', '=', self.id)],
            'context': {'default_pet_id': self.pet_id.id, 'default_consultation_id': self.id},
        }

    def action_view_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'ir.attachment', 'view_mode': 'kanban,list,form',
            'name': _("Files"), 'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': {'default_res_model': self._name, 'default_res_id': self.id},
        }

    def action_hospitalize(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vet.hospitalization', 'view_mode': 'form',
            'name': _("Admit Patient"),
            'context': {'default_pet_id': self.pet_id.id, 'default_consultation_id': self.id,
                        'default_vet_id': self.vet_id.id, 'default_reason': self.reason},
        }

    def action_print_record(self):
        return self.env.ref('odossey_veterinary.action_report_consultation').report_action(self)


class VetConsultationLine(models.Model):
    _name = 'vet.consultation.line'
    _description = 'Consultation Charge'
    _order = 'consultation_id, sequence, id'

    consultation_id = fields.Many2one('vet.consultation', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    pet_id = fields.Many2one(related='consultation_id.pet_id', store=True, string="Patient")
    vet_id = fields.Many2one(related='consultation_id.vet_id', store=True, string="Veterinarian")
    date = fields.Datetime(related='consultation_id.date', store=True)
    state = fields.Selection(related='consultation_id.state', store=True)
    product_id = fields.Many2one('product.product', required=True)
    name = fields.Char(string="Description")
    vet_kind = fields.Selection(related='product_id.vet_kind')
    controlled = fields.Boolean(related='product_id.vet_controlled', store=True, string="Controlled")
    quantity = fields.Float(default=1.0, digits='Product Unit', required=True)
    uom_id = fields.Many2one(related='product_id.uom_id', string="Unit")
    price_unit = fields.Float(string="Unit Price", digits='Product Price')
    price_subtotal = fields.Monetary(compute='_compute_price_subtotal', string="Subtotal")
    currency_id = fields.Many2one(related='consultation_id.currency_id')
    tracking = fields.Selection(related='product_id.tracking')
    lot_id = fields.Many2one('stock.lot', string="Lot", domain="[('product_id', '=', product_id)]")
    note = fields.Char()
    sale_line_id = fields.Many2one('sale.order.line', copy=False, readonly=True)

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            pricelist = self.consultation_id.owner_id.property_product_pricelist
            self.price_unit = pricelist._get_product_price(self.product_id, self.quantity or 1.0) if pricelist else self.product_id.lst_price

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("The quantity must be positive."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('product_id') and 'price_unit' not in vals:
                vals['price_unit'] = self.env['product.product'].browse(vals['product_id']).lst_price
            if vals.get('product_id') and not vals.get('name'):
                vals['name'] = self.env['product.product'].browse(vals['product_id']).display_name
        return super().create(vals_list)

    def _vet_sale_line_vals(self):
        self.ensure_one()
        return {
            'product_id': self.product_id.id,
            'name': self.name or self.product_id.display_name,
            'product_uom_qty': self.quantity,
            'price_unit': self.price_unit,
        }

    def _vet_create_preventive_records(self):
        Vacc = self.env['vet.vaccination']
        for line in self.filtered(lambda l: l.product_id.vet_kind in ('vaccine', 'antiparasitic')):
            consultation = line.consultation_id
            if Vacc.search_count([('consultation_id', '=', consultation.id), ('product_id', '=', line.product_id.id)]):
                continue
            Vacc.create({
                'pet_id': consultation.pet_id.id,
                'product_id': line.product_id.id,
                'date': fields.Date.context_today(line),
                'vet_id': consultation.vet_id.id,
                'consultation_id': consultation.id,
                'lot_id': line.lot_id.id,
            })


class VetPet(models.Model):
    _inherit = 'vet.pet'

    consultation_ids = fields.One2many('vet.consultation', 'pet_id', string="Consultations")
    consultation_count = fields.Integer(compute='_compute_consultation_count')
    last_consultation_date = fields.Datetime(compute='_compute_consultation_count')

    def _compute_consultation_count(self):
        data = {pet: (count, last) for pet, count, last in self.env['vet.consultation']._read_group(
            [('pet_id', 'in', self.ids), ('state', '!=', 'cancel')], ['pet_id'], ['__count', 'date:max'])}
        for pet in self:
            pet.consultation_count, pet.last_consultation_date = data.get(pet, (0, False))

    def action_view_consultations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vet.consultation', 'view_mode': 'list,form',
            'name': _("Medical Record of %s", self.name), 'domain': [('pet_id', '=', self.id)],
            'context': {'default_pet_id': self.id},
        }

    def action_new_consultation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vet.consultation', 'view_mode': 'form',
            'name': _("New Consultation"),
            'context': {'default_pet_id': self.id, 'default_weight': self.weight},
        }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    vet_consultation_id = fields.Many2one('vet.consultation', string="Consultation", copy=False, readonly=True)
    vet_pet_id = fields.Many2one('vet.pet', string="Patient", copy=False)

    def _action_confirm(self):
        res = super()._action_confirm()
        self._vet_assign_consultation_lots()
        return res

    def _vet_assign_consultation_lots(self):
        """Lots chosen in the consultation are used for the delivery of the order."""
        for order in self.filtered('vet_consultation_id'):
            lot_by_product = {l.product_id: l.lot_id for l in order.vet_consultation_id.line_ids if l.lot_id}
            if not lot_by_product:
                continue
            for move in order.picking_ids.move_ids.filtered(lambda m: m.product_id in lot_by_product and m.state not in ('done', 'cancel')):
                lot = lot_by_product[move.product_id]
                move.move_line_ids.unlink()
                move.move_line_ids = [(0, 0, {
                    'product_id': move.product_id.id, 'lot_id': lot.id, 'quantity': move.product_uom_qty,
                    'location_id': move.location_id.id, 'location_dest_id': move.location_dest_id.id,
                    'product_uom_id': move.product_uom.id, 'picking_id': move.picking_id.id,
                })]
