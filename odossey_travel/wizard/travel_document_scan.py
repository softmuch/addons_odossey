from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

from ..tools.id_parsers import DocumentParseError, cuil_check_digit, parse_document

CUIL_PERSON_PREFIXES = ('20', '23', '24', '27')

DOC_TYPES = [
    ('dni_new', "DNI card (PDF417)"),
    ('dni_old', "DNI card, 2009-2012 model (PDF417)"),
    ('dni_electronic', "Electronic DNI (QR)"),
    ('mrz_td3', "Passport (MRZ)"),
    ('mrz_td1', "ID card back side (MRZ)"),
]


class TravelDocumentScan(models.TransientModel):
    """Create or complete a contact by reading the PDF417 barcode of the Argentine DNI
    (handheld 2D scanner in keyboard mode or camera) or the MRZ of a passport."""
    _name = 'travel.document.scan'
    _description = "Scan Identity Document"

    raw_data = fields.Text(
        string="Scanned Data",
        help="Scan the barcode of the DNI with a 2D scanner (keyboard mode), use the camera or "
             "paste the 2 or 3 lines of the MRZ of the passport.")
    input_type = fields.Selection(
        selection=[('auto', "Automatic"), ('dni', "DNI barcode"), ('mrz', "Passport / MRZ")],
        string="Document", default='auto', required=True)
    parse_error = fields.Char(compute='_compute_parsed', store=True)
    parse_warnings = fields.Text(compute='_compute_parsed', store=True)
    doc_type = fields.Selection(DOC_TYPES, string="Detected Document",
                                compute='_compute_parsed', store=True)
    first_names = fields.Char(string="First Names", compute='_compute_parsed', store=True,
                              readonly=False)
    last_name = fields.Char(string="Last Name", compute='_compute_parsed', store=True,
                            readonly=False)
    gender = fields.Selection(
        selection=[('male', "Male"), ('female', "Female"), ('other', "Other")],
        string="Gender", compute='_compute_parsed', store=True, readonly=False)
    birthdate = fields.Date(string="Birthdate", compute='_compute_parsed', store=True,
                            readonly=False)
    dni_number = fields.Char(string="DNI", compute='_compute_parsed', store=True, readonly=False)
    cuil = fields.Char(string="CUIL", compute='_compute_parsed', store=True, readonly=False)
    dni_tramite = fields.Char(string="Procedure Number", compute='_compute_parsed', store=True,
                              readonly=False)
    dni_ejemplar = fields.Char(string="Copy", compute='_compute_parsed', store=True,
                               readonly=False)
    passport_number = fields.Char(string="Passport Number", compute='_compute_parsed',
                                  store=True, readonly=False)
    passport_country_id = fields.Many2one('res.country', string="Issuing Country",
                                          compute='_compute_parsed', store=True, readonly=False)
    issue_date = fields.Date(string="Issue Date", compute='_compute_parsed', store=True,
                             readonly=False)
    expiry_date = fields.Date(string="Expiry Date", compute='_compute_parsed', store=True,
                              readonly=False)
    nationality_id = fields.Many2one('res.country', string="Nationality",
                                     compute='_compute_parsed', store=True, readonly=False)
    partner_id = fields.Many2one(
        'res.partner', string="Contact", compute='_compute_partner_id', store=True,
        readonly=False, domain="[('is_company', '=', False)]",
        help="Existing contact that will be completed. Leave empty to create a new contact.")
    sale_order_id = fields.Many2one('sale.order', string="Add to Booking")
    consent = fields.Boolean(
        string="Consent",
        help="The passenger was informed and consents to the processing of their personal data "
             "for the management of the trip (Law 25.326).")

    @api.depends('raw_data', 'input_type')
    def _compute_parsed(self):
        Country = self.env['res.country']
        for wizard in self:
            result = {}
            wizard.parse_error = False
            wizard.parse_warnings = False
            if wizard.raw_data and wizard.raw_data.strip():
                try:
                    result = parse_document(wizard.raw_data, wizard.input_type)
                except DocumentParseError as e:
                    wizard.parse_error = str(e)
            wizard.parse_warnings = "\n".join(result.get('warnings') or []) or False
            wizard.doc_type = result.get('doc_type')
            for key in ('first_names', 'last_name', 'gender', 'birthdate', 'dni_number', 'cuil',
                        'dni_tramite', 'dni_ejemplar', 'passport_number', 'issue_date'):
                wizard[key] = result.get(key) or False
            wizard.expiry_date = result.get('expiry_date') or False
            nationality = result.get('nationality_code2')
            issuing = result.get('issuing_country_code2')
            wizard.nationality_id = nationality and Country.search(
                [('code', '=', nationality)], limit=1)
            wizard.passport_country_id = (issuing and result.get('doc_type') == 'mrz_td3'
                                          and Country.search([('code', '=', issuing)], limit=1))

    @api.model
    def _dni_vat_domain(self, dni):
        """Domain of the people identified by the DNI ``dni``: the DNI itself or a CUIL/CUIT
        of a person (prefix 20, 23, 24 or 27) built on it."""
        dni8 = dni.zfill(8)
        exact = {dni, dni8, f"{int(dni):,}".replace(',', '.')}
        cuils = []
        for prefix in CUIL_PERSON_PREFIXES:
            check = cuil_check_digit(prefix + dni8)
            if check is not None:
                cuils += [f"{prefix}{dni8}{check}", f"{prefix}-{dni8}-{check}"]
        return [('is_company', '=', False), ('vat', 'in', sorted(exact) + cuils)]

    @staticmethod
    def _vat_digits(vat):
        return ''.join(c for c in (vat or '') if c.isdigit())

    @api.depends('dni_number', 'passport_number')
    def _compute_partner_id(self):
        Partner = self.env['res.partner']
        for wizard in self:
            if self.env.context.get('travel_scan_partner_id'):
                wizard.partner_id = self.env.context['travel_scan_partner_id']
                continue
            partner = Partner
            dni = self._vat_digits(wizard.dni_number).lstrip('0')
            if dni and len(dni) <= 8:
                partner = Partner.search(self._dni_vat_domain(dni), limit=1)
            if not partner and wizard.passport_number:
                partner = Partner.search([('passport_number', '=', wizard.passport_number),
                                          ('is_company', '=', False)], limit=1)
            wizard.partner_id = partner

    @api.model
    def action_open(self, partner=None, sale_order=None):
        context = {'default_sale_order_id': sale_order.id if sale_order else False}
        if partner:
            context['travel_scan_partner_id'] = partner.id
        return {
            'name': self.env._("Scan Identity Document"),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def _prepare_partner_values(self):
        self.ensure_one()
        vals = {}
        name = " ".join(filter(None, [self.first_names, self.last_name]))
        partner = self.partner_id
        if name and (not partner or not partner.name):
            vals['name'] = name
        for field in ('gender', 'birthdate', 'dni_tramite', 'dni_ejemplar', 'passport_number'):
            if self[field]:
                vals[field] = self[field]
        if self.nationality_id:
            vals['nationality_id'] = self.nationality_id.id
        if self.doc_type == 'mrz_td3':
            vals.update({
                'passport_country_id': self.passport_country_id.id,
                'passport_expiry_date': self.expiry_date,
            })
        partner_vat = self._vat_digits(partner.vat).lstrip('0')
        dni = self._vat_digits(self.dni_number).lstrip('0')
        if dni and (not partner.vat or partner_vat == dni):
            # never replace a CUIL/CUIT (or another document) already set on the contact
            vals.update({
                'vat': self.dni_number,
                'l10n_latam_identification_type_id': self.env.ref('l10n_ar.it_dni').id,
            })
        elif self.passport_number and not (partner and partner.vat):
            vals.update({
                'vat': self.passport_number,
                'l10n_latam_identification_type_id': self.env.ref('l10n_latam_base.it_pass').id,
            })
        if not partner.l10n_ar_afip_responsibility_type_id:
            # travellers are invoiced as final consumers (Factura B) unless told otherwise
            vals['l10n_ar_afip_responsibility_type_id'] = self.env.ref('l10n_ar.res_CF').id
        if not partner or not partner.country_id:
            country = self.nationality_id or self.passport_country_id
            if country:
                vals['country_id'] = country.id
        return vals

    def action_apply(self):
        self.ensure_one()
        if self.parse_error:
            raise UserError(self.parse_error)
        if not (self.first_names or self.last_name or self.partner_id):
            raise UserError(self.env._("Scan a document first."))
        if not self.consent:
            raise UserError(self.env._(
                "Confirm that the passenger consents to the processing of their personal data."))
        if self.partner_id.is_company:
            raise UserError(self.env._(
                "%s is a company: personal data can only be loaded on an individual.",
                self.partner_id.display_name))
        vals = self._prepare_partner_values()
        if self.partner_id:
            partner = self.partner_id
            partner.write(vals)
        else:
            partner = self.env['res.partner'].create(vals)
        partner.message_post(body=self.env._(
            "Personal data loaded from the %s (consent of the passenger recorded by %s).",
            dict(DOC_TYPES).get(self.doc_type, self.env._("document")), self.env.user.name))
        if self.sale_order_id:
            order = self.sale_order_id
            if partner not in order.travel_passenger_ids.partner_id:
                order.travel_passenger_ids = [Command.create({'partner_id': partner.id})]
            return {'type': 'ir.actions.act_window_close'}
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': partner.id,
            'view_mode': 'form',
            'target': 'current',
        }
