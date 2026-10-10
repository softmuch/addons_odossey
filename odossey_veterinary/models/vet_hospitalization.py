import math
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class VetHospitalization(models.Model):
    _name = 'vet.hospitalization'
    _description = 'Hospitalization'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'admission_date desc, id desc'

    name = fields.Char(string="Reference", readonly=True, copy=False, default=lambda self: _("New"))
    state = fields.Selection([('admitted', "Admitted"), ('discharged', "Discharged"), ('cancel', "Cancelled")],
                             default='admitted', required=True, tracking=True)
    pet_id = fields.Many2one('vet.pet', string="Patient", required=True, tracking=True, index=True)
    owner_id = fields.Many2one(related='pet_id.owner_id', store=True, string="Owner")
    pet_alert_summary = fields.Char(related='pet_id.alert_summary')
    pet_has_danger_alert = fields.Boolean(related='pet_id.has_danger_alert')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    consultation_id = fields.Many2one('vet.consultation', string="Origin Consultation")
    vet_id = fields.Many2one('res.users', string="Responsible Veterinarian", required=True,
                             default=lambda self: self.env.user if self.env.user.vet_is_veterinarian else False,
                             domain="[('vet_is_veterinarian', '=', True)]")
    admission_date = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True)
    discharge_date = fields.Datetime(tracking=True)
    cage = fields.Char(string="Cage / Ward")
    reason = fields.Char(string="Reason for Admission", required=True)
    isolation = fields.Boolean(help="Infectious patient (parvovirus, distemper...): isolation ward and protective equipment.")
    diet = fields.Char(string="Diet / Feeding")
    task_ids = fields.One2many('vet.hospitalization.task', 'hospitalization_id', string="Treatment Sheet")
    pending_task_count = fields.Integer(compute='_compute_task_counts')
    overdue_task_count = fields.Integer(compute='_compute_task_counts')
    day_product_id = fields.Many2one('product.product', string="Daily Charge",
                                     default=lambda self: self._default_day_product(),
                                     help="Service charged for each started day of hospitalization.")
    days = fields.Integer(compute='_compute_days', string="Days")
    discharge_summary = fields.Html(string="Discharge Summary",
                                    help="Clinical summary (epicrisis): evolution, treatments received, indications for home.")
    sale_order_id = fields.Many2one('sale.order', readonly=True, copy=False)

    @api.model
    def _default_day_product(self):
        product_id = self.env['ir.config_parameter'].sudo().get_param('odossey_veterinary.hospitalization_product_id')
        product = self.env['product.product'].browse(int(product_id)).exists() if product_id else False
        return product or self.env.ref('odossey_veterinary.product_service_hospitalization_day', raise_if_not_found=False)

    @api.depends('admission_date', 'discharge_date')
    def _compute_days(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.admission_date:
                rec.days = 0
                continue
            end = rec.discharge_date or now
            rec.days = max(1, math.ceil((end - rec.admission_date).total_seconds() / 86400))

    def _compute_task_counts(self):
        now = fields.Datetime.now()
        for rec in self:
            pending = rec.task_ids.filtered(lambda t: t.state == 'pending')
            rec.pending_task_count = len(pending)
            rec.overdue_task_count = len(pending.filtered(lambda t: t.scheduled_at and t.scheduled_at < now))

    @api.constrains('admission_date', 'discharge_date')
    def _check_dates(self):
        for rec in self:
            if rec.discharge_date and rec.discharge_date < rec.admission_date:
                raise ValidationError(_("The discharge date cannot be before the admission date."))

    @api.constrains('pet_id', 'state')
    def _check_single_admission(self):
        for rec in self.filtered(lambda r: r.state == 'admitted'):
            if self.search_count([('pet_id', '=', rec.pet_id.id), ('state', '=', 'admitted'), ('id', '!=', rec.id)]):
                raise ValidationError(_("%s is already admitted.", rec.pet_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('vet.hospitalization') or _("New")
        records = super().create(vals_list)
        for rec in records:
            rec.pet_id.message_post(body=_("Admitted to hospital: %s", rec._get_html_link()))
        return records

    def action_discharge(self):
        for rec in self:
            pending = rec.task_ids.filtered(lambda t: t.state == 'pending' and t.scheduled_at and t.scheduled_at <= fields.Datetime.now())
            pending.write({'state': 'skipped', 'note': _("Not done before discharge")})
            rec.task_ids.filtered(lambda t: t.state == 'pending').unlink()
            rec.write({'state': 'discharged', 'discharge_date': rec.discharge_date or fields.Datetime.now()})
            rec._vet_create_sale_order()

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reopen(self):
        self.write({'state': 'admitted', 'discharge_date': False})

    def _vet_create_sale_order(self):
        for rec in self.filtered(lambda r: not r.sale_order_id):
            lines = []
            if rec.day_product_id:
                lines.append((0, 0, {'product_id': rec.day_product_id.id, 'product_uom_qty': rec.days,
                                     'name': _("%(product)s - %(pet)s (%(days)s days)", product=rec.day_product_id.display_name,
                                               pet=rec.pet_id.name, days=rec.days)}))
            qty_by_product = {}
            for task in rec.task_ids.filtered(lambda t: t.state == 'done' and t.product_id and t.chargeable):
                qty_by_product[task.product_id] = qty_by_product.get(task.product_id, 0.0) + (task.quantity or 1.0)
            for product, qty in qty_by_product.items():
                lines.append((0, 0, {'product_id': product.id, 'product_uom_qty': qty}))
            if not lines:
                continue
            order = self.env['sale.order'].create({
                'partner_id': rec.owner_id.id, 'origin': rec.name, 'vet_pet_id': rec.pet_id.id,
                'company_id': rec.company_id.id, 'order_line': lines,
            })
            rec.sale_order_id = order
            rec.message_post(body=_("Sale order %s created.", order._get_html_link()))

    def action_view_sale_order(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'sale.order', 'res_id': self.sale_order_id.id, 'view_mode': 'form'}

    def action_schedule_treatment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vet.hospitalization.schedule.wizard', 'view_mode': 'form',
            'target': 'new', 'name': _("Schedule Treatment"), 'context': {'default_hospitalization_id': self.id},
        }

    def action_print_discharge(self):
        return self.env.ref('odossey_veterinary.action_report_discharge').report_action(self)


class VetHospitalizationTask(models.Model):
    _name = 'vet.hospitalization.task'
    _description = 'Hospitalization Treatment Task'
    _order = 'scheduled_at, id'

    hospitalization_id = fields.Many2one('vet.hospitalization', required=True, ondelete='cascade', index=True)
    pet_id = fields.Many2one(related='hospitalization_id.pet_id', store=True, string="Patient")
    cage = fields.Char(related='hospitalization_id.cage')
    hospitalization_state = fields.Selection(related='hospitalization_id.state', store=True, string="Hospitalization Status")
    task_type = fields.Selection([
        ('medication', "Medication"), ('fluids', "Fluid therapy"), ('feeding', "Feeding"),
        ('vitals', "Vital signs"), ('walk', "Walk / hygiene"), ('procedure', "Procedure"), ('observation', "Observation"),
    ], string="Type", default='medication', required=True)
    name = fields.Char(string="Description", required=True)
    product_id = fields.Many2one('product.product', string="Product")
    dose = fields.Char()
    route = fields.Selection(related='product_id.vet_route', readonly=False)
    quantity = fields.Float(default=1.0, digits='Product Unit')
    chargeable = fields.Boolean(default=True, help="Charge the product on the hospitalization order when done.")
    scheduled_at = fields.Datetime(string="Scheduled", required=True, default=fields.Datetime.now)
    state = fields.Selection([('pending', "Pending"), ('done', "Done"), ('skipped', "Skipped")],
                             default='pending', required=True)
    is_overdue = fields.Boolean(compute='_compute_is_overdue')
    done_at = fields.Datetime(readonly=True)
    done_by_id = fields.Many2one('res.users', string="Done By", readonly=True)
    temperature = fields.Float(string="Temp. (°C)", digits=(4, 1))
    heart_rate = fields.Integer(string="HR")
    respiratory_rate = fields.Integer(string="RR")
    note = fields.Char()

    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for task in self:
            task.is_overdue = task.state == 'pending' and bool(task.scheduled_at) and task.scheduled_at < now

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and not self.name:
            self.name = self.product_id.display_name

    def action_done(self):
        if self.filtered(lambda t: t.hospitalization_state != 'admitted'):
            raise UserError(_("The patient is no longer admitted."))
        self.write({'state': 'done', 'done_at': fields.Datetime.now(), 'done_by_id': self.env.uid})

    def action_skip(self):
        self.write({'state': 'skipped', 'done_at': fields.Datetime.now(), 'done_by_id': self.env.uid})

    def action_reset(self):
        self.write({'state': 'pending', 'done_at': False, 'done_by_id': False})


class VetHospitalizationScheduleWizard(models.TransientModel):
    _name = 'vet.hospitalization.schedule.wizard'
    _description = 'Schedule a Repeated Treatment'

    hospitalization_id = fields.Many2one('vet.hospitalization', required=True)
    kind = fields.Selection([
        ('medication', "Medication"), ('fluids', "Fluid therapy"), ('feeding', "Feeding"),
        ('vitals', "Vital signs"), ('walk', "Walk / hygiene"), ('procedure', "Procedure"), ('observation', "Observation"),
    ], string="Type", default='medication', required=True)
    name = fields.Char(string="Description")
    product_id = fields.Many2one('product.product', string="Product")
    dose = fields.Char()
    quantity = fields.Float(default=1.0, digits='Product Unit')
    start = fields.Datetime(required=True, default=fields.Datetime.now)
    every_hours = fields.Integer(string="Every (hours)", default=8, required=True)
    duration_days = fields.Float(string="During (days)", default=3, required=True)

    def action_schedule(self):
        self.ensure_one()
        if self.every_hours <= 0 or self.duration_days <= 0:
            raise UserError(_("Interval and duration must be positive."))
        count = int(self.duration_days * 24 // self.every_hours) or 1
        name = self.name or self.product_id.display_name or dict(self._fields['kind']._description_selection(self.env))[self.kind]
        self.env['vet.hospitalization.task'].create([{
            'hospitalization_id': self.hospitalization_id.id,
            'task_type': self.kind,
            'name': name,
            'product_id': self.product_id.id,
            'dose': self.dose,
            'quantity': self.quantity,
            'scheduled_at': self.start + timedelta(hours=self.every_hours * i),
        } for i in range(count)])
        return {'type': 'ir.actions.act_window_close'}


class VetPet(models.Model):
    _inherit = 'vet.pet'

    hospitalization_ids = fields.One2many('vet.hospitalization', 'pet_id')
    hospitalization_count = fields.Integer(compute='_compute_hospitalization_count')
    is_hospitalized = fields.Boolean(compute='_compute_hospitalization_count')

    def _compute_hospitalization_count(self):
        for pet in self:
            pet.hospitalization_count = len(pet.hospitalization_ids)
            pet.is_hospitalized = any(h.state == 'admitted' for h in pet.hospitalization_ids)

    def action_view_hospitalizations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'vet.hospitalization', 'view_mode': 'list,form',
            'name': _("Hospitalizations"), 'domain': [('pet_id', '=', self.id)], 'context': {'default_pet_id': self.id},
        }
