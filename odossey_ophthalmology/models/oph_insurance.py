from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class OphInsurance(models.Model):
    _name = 'oph.insurance'
    _description = 'Health Insurance (Obra Social / Prepaga)'
    _inherit = ['mail.thread']
    _order = 'sequence, name'

    name = fields.Char(required=True, tracking=True)
    short_name = fields.Char(string="Acronym", help="Short name used in lists and on the agenda. Example: OSDE, PAMI.")
    sequence = fields.Integer(default=10)
    insurance_type = fields.Selection([
        ('obra_social', "Obra social"), ('prepaga', "Prepaid medicine"), ('pami', "PAMI"),
        ('provincial', "Provincial obra social"), ('art', "Occupational risk (ART)"), ('mutual', "Mutual"),
        ('other', "Other"),
    ], string="Type", default='obra_social', required=True)
    registry_code = fields.Char(string="Registry Code",
                                help="Code in the National Registry of Health Insurers (RNOS / RNEMP).")
    partner_id = fields.Many2one('res.partner', string="Invoicing Partner", tracking=True,
                                 help="Company that receives the monthly settlement invoice (CUIT, address, "
                                      "tax condition). Created automatically if left empty.")
    plan_ids = fields.One2many('oph.insurance.plan', 'insurance_id', string="Plans")
    price_ids = fields.One2many('oph.insurance.price', 'insurance_id', string="Agreed Fees")
    requires_authorization = fields.Boolean(
        string="Requires Prior Authorization", tracking=True,
        help="Surgeries and studies covered by this insurer need an authorization number before they are done.")
    default_copay = fields.Monetary(string="Default Co-payment", currency_field='currency_id',
                                   help="Amount the patient pays for a consultation when no specific fee is set.")
    settlement_day = fields.Integer(string="Settlement Day", default=5,
                                    help="Day of the month when the services of the previous month are presented.")
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id, required=True)
    notes = fields.Html(help="Agreement conditions, contact of the provider department, how to present the claims.")
    patient_count = fields.Integer(compute='_compute_patient_count')
    color = fields.Integer()
    active = fields.Boolean(default=True)

    def _compute_patient_count(self):
        data = dict(self.env['res.partner']._read_group([('oph_insurance_id', 'in', self.ids)],
                                                        ['oph_insurance_id'], ['__count']))
        for insurance in self:
            insurance.patient_count = data.get(insurance, 0)

    @api.depends('name', 'short_name')
    def _compute_display_name(self):
        for insurance in self:
            insurance.display_name = insurance.short_name or insurance.name

    @api.model_create_multi
    def create(self, vals_list):
        insurances = super().create(vals_list)
        insurances._ensure_partner()
        return insurances

    def _ensure_partner(self):
        for insurance in self.filtered(lambda i: not i.partner_id):
            insurance.partner_id = self.env['res.partner'].create({
                'name': insurance.name, 'is_company': True, 'customer_rank': 1,
            })

    def _get_price(self, product, plan=None):
        """Agreed fee for a product: plan specific first, then the insurer's general fee."""
        self.ensure_one()
        prices = self.price_ids.filtered(lambda p: p.product_id == product.product_tmpl_id and p.active)
        return prices.filtered(lambda p: plan and p.plan_id == plan)[:1] or prices.filtered(lambda p: not p.plan_id)[:1]

    def action_view_patients(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_ophthalmology.oph_patient_action')
        action['domain'] = [('oph_insurance_id', '=', self.id)]
        return action


class OphInsurancePlan(models.Model):
    _name = 'oph.insurance.plan'
    _description = 'Health Insurance Plan'
    _order = 'insurance_id, name'

    name = fields.Char(required=True)
    insurance_id = fields.Many2one('oph.insurance', required=True, ondelete='cascade', index=True)
    active = fields.Boolean(default=True)

    @api.depends('name', 'insurance_id')
    def _compute_display_name(self):
        for plan in self:
            plan.display_name = '%s %s' % (plan.insurance_id.display_name or '', plan.name or '')


class OphInsurancePrice(models.Model):
    _name = 'oph.insurance.price'
    _description = 'Agreed Fee (Nomenclator)'
    _order = 'insurance_id, nomenclator_code, id'

    insurance_id = fields.Many2one('oph.insurance', required=True, ondelete='cascade', index=True)
    plan_id = fields.Many2one('oph.insurance.plan', string="Plan", domain="[('insurance_id', '=', insurance_id)]",
                              help="Leave empty when the fee applies to every plan of the insurer.")
    product_id = fields.Many2one('product.template', string="Service", required=True, ondelete='cascade')
    nomenclator_code = fields.Char(string="Nomenclator Code",
                                   help="Code of the service in the insurer's nomenclator. Example: 30.01.01 consultation.")
    insurance_amount = fields.Monetary(string="Paid by Insurer", currency_field='currency_id',
                                       help="Amount the insurer pays for the service (billed in the monthly settlement).")
    copay_amount = fields.Monetary(string="Co-payment", currency_field='currency_id',
                                   help="Amount the patient pays at the reception (bono / coseguro).")
    requires_authorization = fields.Boolean(string="Needs Authorization")
    currency_id = fields.Many2one(related='insurance_id.currency_id')
    active = fields.Boolean(default=True)

    @api.constrains('insurance_amount', 'copay_amount')
    def _check_amounts(self):
        for price in self:
            if price.insurance_amount < 0 or price.copay_amount < 0:
                raise ValidationError(_("Fees cannot be negative."))
