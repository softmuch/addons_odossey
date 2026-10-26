import base64
import csv
import io

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class OphCharge(models.Model):
    """Service or product used in an exam, study or surgery. When the record is closed every charge is billed:
    to the health insurance (agreed fee, monthly settlement) and / or to the patient (co-payment or private price)."""
    _name = 'oph.charge'
    _description = 'Clinical Charge'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    exam_id = fields.Many2one('oph.exam', index='btree_not_null', ondelete='cascade')
    study_id = fields.Many2one('oph.study', index='btree_not_null', ondelete='cascade')
    surgery_id = fields.Many2one('oph.surgery', index='btree_not_null', ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product / Service", required=True)
    name = fields.Char(string="Description")
    quantity = fields.Float(default=1.0, digits='Product Unit')
    tracking = fields.Selection(related='product_id.tracking')
    lot_id = fields.Many2one('stock.lot', string="Lot / Serial", domain="[('product_id', '=', product_id)]")
    billing = fields.Selection([('auto', "Automatic"), ('private', "Private (patient pays)"),
                                ('free', "No charge")], default='auto', required=True,
                               help="Automatic: covered by the health insurance when it has an agreed fee for the "
                                    "service, otherwise private. No charge: courtesy or included in a surgical package.")
    sale_line_id = fields.Many2one('sale.order.line', string="Sale Line", readonly=True, copy=False)
    claim_id = fields.Many2one('oph.insurance.claim', string="Insurance Service", readonly=True, copy=False)
    billed = fields.Boolean(compute='_compute_billed')

    def _compute_billed(self):
        for line in self:
            line.billed = bool(line.sale_line_id or line.claim_id) or line.billing == 'free'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name

    def _oph_bill(self, patient, insurance, plan, authorization, origin):
        """Create the insurance services and the patient quotation of the charges not billed yet."""
        lines = self.filtered(lambda l: not l.sale_line_id and not l.claim_id and l.billing != 'free')
        if not lines:
            return self.env['sale.order']
        so_lines = []
        for line in lines:
            price = insurance._get_price(line.product_id, plan) if insurance and line.billing == 'auto' else False
            if price:
                line.claim_id = self.env['oph.insurance.claim'].create({
                    'patient_id': patient.id, 'insurance_id': insurance.id, 'plan_id': plan.id if plan else False,
                    'member_number': patient.oph_member_number, 'product_id': line.product_id.id,
                    'nomenclator_code': price.nomenclator_code or line.product_id.oph_nomenclator_code,
                    'quantity': line.quantity, 'unit_amount': price.insurance_amount,
                    'copay_amount': price.copay_amount * line.quantity,
                    'authorization': authorization,
                    'date': fields.Date.context_today(self),
                    'exam_id': origin.id if origin._name == 'oph.exam' else False,
                    'study_id': origin.id if origin._name == 'oph.study' else False,
                    'surgery_id': origin.id if origin._name == 'oph.surgery' else False,
                    'state': 'pending' if price.requires_authorization and not authorization else 'to_bill',
                })
                if price.copay_amount:
                    so_lines.append((line, {'price_unit': price.copay_amount,
                                            'name': _("%(product)s - co-payment %(insurer)s",
                                                      product=line.name or line.product_id.display_name,
                                                      insurer=insurance.display_name)}))
            else:
                so_lines.append((line, {}))
        if not so_lines:
            return self.env['sale.order']
        order = self.env['sale.order'].create({
            'partner_id': patient.id,
            'origin': origin.name,
            'oph_exam_id': origin.id if origin._name == 'oph.exam' else False,
            'oph_surgery_id': origin.id if origin._name == 'oph.surgery' else False,
            'oph_study_id': origin.id if origin._name == 'oph.study' else False,
        })
        for line, extra in so_lines:
            vals = {'order_id': order.id, 'product_id': line.product_id.id, 'product_uom_qty': line.quantity}
            if line.name:
                vals['name'] = line.name
            vals.update(extra)
            line.sale_line_id = self.env['sale.order.line'].create(vals)
        origin.message_post(body=_("Quotation %s created for the patient.", order.name))
        return order


class OphInsuranceClaim(models.Model):
    _name = 'oph.insurance.claim'
    _description = 'Health Insurance Service (Prestación)'
    _order = 'date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    patient_id = fields.Many2one('res.partner', string="Patient", required=True, index=True, ondelete='restrict')
    insurance_id = fields.Many2one('oph.insurance', string="Health Insurance", required=True, index=True)
    plan_id = fields.Many2one('oph.insurance.plan', string="Plan")
    member_number = fields.Char(string="Member No.")
    product_id = fields.Many2one('product.product', string="Service", required=True)
    nomenclator_code = fields.Char(string="Code")
    quantity = fields.Float(default=1.0)
    unit_amount = fields.Monetary(string="Unit Fee", currency_field='currency_id')
    amount = fields.Monetary(compute='_compute_amount', store=True, currency_field='currency_id')
    copay_amount = fields.Monetary(string="Co-payment", currency_field='currency_id',
                                   help="Paid by the patient at the reception, not included in the settlement.")
    currency_id = fields.Many2one(related='insurance_id.currency_id')
    authorization = fields.Char(string="Authorization")
    exam_id = fields.Many2one('oph.exam', string="Exam", index='btree_not_null', ondelete='set null')
    study_id = fields.Many2one('oph.study', string="Study", index='btree_not_null', ondelete='set null')
    surgery_id = fields.Many2one('oph.surgery', string="Surgery", index='btree_not_null', ondelete='set null')
    settlement_id = fields.Many2one('oph.insurance.settlement', string="Settlement", index='btree_not_null',
                                    ondelete='set null', copy=False)
    state = fields.Selection([
        ('pending', "Waiting Authorization"), ('to_bill', "To Bill"), ('billed', "Billed"), ('rejected', "Rejected"),
    ], default='to_bill', required=True, index=True)
    rejection_reason = fields.Char(string="Rejection Reason",
                                   help="Debit (débito) applied by the insurer. The service can be presented again.")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    @api.depends('nomenclator_code', 'product_id', 'patient_id')
    def _compute_name(self):
        for claim in self:
            claim.name = '%s %s - %s' % (claim.nomenclator_code or '', claim.product_id.name or '', claim.patient_id.name or '')

    @api.depends('quantity', 'unit_amount')
    def _compute_amount(self):
        for claim in self:
            claim.amount = claim.quantity * claim.unit_amount

    def action_authorize(self):
        for claim in self:
            if not claim.authorization:
                raise UserError(_("Write the authorization number first."))
        self.filtered(lambda c: c.state == 'pending').write({'state': 'to_bill'})

    def action_reject(self):
        for claim in self:
            if not claim.rejection_reason:
                raise UserError(_("Write the rejection reason given by the insurer."))
        self.write({'state': 'rejected'})

    def action_rebill(self):
        """A rejected service is presented again in the next settlement."""
        self.filtered(lambda c: c.state == 'rejected').write({'state': 'to_bill', 'settlement_id': False})


class OphInsuranceSettlement(models.Model):
    _name = 'oph.insurance.settlement'
    _description = 'Monthly Settlement to Health Insurance'
    _inherit = ['mail.thread']
    _order = 'date_to desc, id desc'

    name = fields.Char(string="Reference", required=True, readonly=True, copy=False, default=lambda self: _("New"))
    insurance_id = fields.Many2one('oph.insurance', string="Health Insurance", required=True, tracking=True)
    date_from = fields.Date(string="From", required=True,
                            default=lambda self: fields.Date.context_today(self).replace(day=1) - relativedelta(months=1))
    date_to = fields.Date(string="To", required=True,
                          default=lambda self: fields.Date.context_today(self).replace(day=1) - relativedelta(days=1))
    claim_ids = fields.One2many('oph.insurance.claim', 'settlement_id', string="Services")
    claim_count = fields.Integer(compute='_compute_totals')
    amount_total = fields.Monetary(compute='_compute_totals', currency_field='currency_id', string="Total")
    currency_id = fields.Many2one(related='insurance_id.currency_id')
    invoice_id = fields.Many2one('account.move', string="Invoice", readonly=True, copy=False)
    payment_state = fields.Selection(related='invoice_id.payment_state', string="Payment Status")
    state = fields.Selection([('draft', "Draft"), ('invoiced', "Invoiced"), ('cancel', "Cancelled")],
                             default='draft', required=True, tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    @api.depends('claim_ids.amount')
    def _compute_totals(self):
        for settlement in self:
            settlement.claim_count = len(settlement.claim_ids)
            settlement.amount_total = sum(settlement.claim_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('oph.insurance.settlement') or _("New")
        return super().create(vals_list)

    def action_load_claims(self):
        for settlement in self:
            if settlement.state != 'draft':
                raise UserError(_("Only draft settlements can be updated."))
            claims = self.env['oph.insurance.claim'].search([
                ('insurance_id', '=', settlement.insurance_id.id), ('state', '=', 'to_bill'),
                ('settlement_id', '=', False), ('date', '<=', settlement.date_to),
            ])
            claims.settlement_id = settlement
            settlement.message_post(body=_("%s services added.", len(claims)))

    def action_create_invoice(self):
        for settlement in self:
            if settlement.state != 'draft':
                continue
            claims = settlement.claim_ids.filtered(lambda c: c.state == 'to_bill')
            if not claims:
                raise UserError(_("There are no services to bill in %s.", settlement.name))
            settlement.insurance_id._ensure_partner()
            lines = []
            for claim in claims.sorted(lambda c: (c.date, c.patient_id.name or '')):
                lines.append((0, 0, {
                    'product_id': claim.product_id.id,
                    'name': '%s - %s (%s %s) - %s%s' % (
                        claim.nomenclator_code or claim.product_id.name, claim.patient_id.name,
                        _("Member"), claim.member_number or '-', fields.Date.to_string(claim.date),
                        (' - %s %s' % (_("Auth."), claim.authorization)) if claim.authorization else ''),
                    'quantity': claim.quantity,
                    'price_unit': claim.unit_amount,
                    'tax_ids': [(6, 0, [])],  # medical services to health insurers are VAT exempt in Argentina
                }))
            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': settlement.insurance_id.partner_id.id,
                'invoice_origin': settlement.name,
                'ref': _("Services %(from)s - %(to)s", **{'from': settlement.date_from, 'to': settlement.date_to}),
                'invoice_line_ids': lines,
            })
            claims.write({'state': 'billed'})
            settlement.write({'invoice_id': invoice.id, 'state': 'invoiced'})

    def action_view_invoice(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'res_id': self.invoice_id.id,
                'view_mode': 'form'}

    def action_cancel(self):
        for settlement in self:
            if settlement.invoice_id and settlement.invoice_id.state == 'posted':
                raise UserError(_("Cancel or credit the invoice %s first.", settlement.invoice_id.name))
            settlement.claim_ids.filtered(lambda c: c.state == 'billed').write({'state': 'to_bill'})
            settlement.claim_ids.write({'settlement_id': False})
            settlement.state = 'cancel'

    def action_export_csv(self):
        """Detail of the services in the format usually requested by the insurers (one line per service)."""
        self.ensure_one()
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow([_("Date"), _("Patient"), _("ID Number"), _("Member No."), _("Plan"), _("Code"),
                         _("Service"), _("Quantity"), _("Fee"), _("Total"), _("Authorization")])
        for claim in self.claim_ids.sorted(lambda c: (c.date, c.patient_id.name or '')):
            writer.writerow([fields.Date.to_string(claim.date), claim.patient_id.name, claim.patient_id.oph_document or '',
                             claim.member_number or '', claim.plan_id.name or '', claim.nomenclator_code or '',
                             claim.product_id.name, claim.quantity, '%.2f' % claim.unit_amount, '%.2f' % claim.amount,
                             claim.authorization or ''])
        attachment = self.env['ir.attachment'].create({
            'name': '%s.csv' % self.name.replace('/', '-'),
            'datas': base64.b64encode(buffer.getvalue().encode('utf-8-sig')),
            'res_model': self._name, 'res_id': self.id, 'mimetype': 'text/csv',
        })
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id, 'target': 'self'}

    def action_print(self):
        return self.env.ref('odossey_ophthalmology.action_report_settlement').report_action(self)

    def _get_report_base_filename(self):
        self.ensure_one()
        return self.name
