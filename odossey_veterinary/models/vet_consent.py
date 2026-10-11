import base64
import hashlib

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

SIGNED_LOCKED_FIELDS = {'pet_id', 'template_id', 'content', 'procedure', 'signature', 'signed_by', 'signed_on',
                        'signature_hash', 'signed_ip'}


class VetConsentTemplate(models.Model):
    _name = 'vet.consent.template'
    _description = 'Informed Consent Template'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    body = fields.Html(string="Consent Text", translate=True, sanitize=True, required=True,
                       help="Placeholders replaced when the consent is prepared: {pet}, {species}, {owner}, "
                            "{procedure}, {date}, {vet}, {company}.")

    def _render_body(self, pet, procedure=None, vet=None):
        self.ensure_one()
        owner = pet.owner_id
        values = {
            '{pet}': escape(pet.name or ''),
            '{species}': escape(pet.species_id.with_context(lang=owner.lang or self.env.lang).name or ''),
            '{owner}': escape(owner.name or ''),
            '{procedure}': escape(procedure or self.with_context(lang=owner.lang or self.env.lang).name),
            '{date}': escape(format_date(self.env, fields.Date.context_today(self), lang_code=owner.lang or self.env.lang)),
            '{vet}': escape((vet or self.env.user).name or ''),
            '{company}': escape(self.env.company.name),
        }
        body = str(self.with_context(lang=owner.lang or self.env.lang).body or '')
        for key, value in values.items():
            body = body.replace(key, value)
        return Markup(body)


class VetConsent(models.Model):
    _name = 'vet.consent'
    _description = 'Informed Consent'
    _inherit = ['portal.mixin', 'mail.thread']
    _order = 'create_date desc, id desc'

    name = fields.Char(string="Reference", required=True, readonly=True, copy=False, default=lambda self: _("New"))
    pet_id = fields.Many2one('vet.pet', string="Patient", required=True, index=True, ondelete='restrict', tracking=True)
    owner_id = fields.Many2one(related='pet_id.owner_id', store=True, string="Owner")
    template_id = fields.Many2one('vet.consent.template', string="Template", required=True, ondelete='restrict')
    title = fields.Char(related='template_id.name', string="Title")
    procedure = fields.Char(help="Procedure the consent is for (e.g. Ovariohysterectomy). Defaults to the template title.")
    consultation_id = fields.Many2one('vet.consultation', string="Consultation", index='btree_not_null')
    hospitalization_id = fields.Many2one('vet.hospitalization', string="Hospitalization", index='btree_not_null')
    vet_id = fields.Many2one('res.users', string="Veterinarian", default=lambda self: self.env.user)
    content = fields.Html(string="Text", sanitize=True, help="Text accepted by the owner; locked once signed.")
    state = fields.Selection([
        ('draft', "Draft"), ('sent', "Waiting Signature"), ('signed', "Signed"), ('refused', "Refused"), ('revoked', "Revoked"),
    ], default='draft', required=True, tracking=True, copy=False)
    signature = fields.Binary(copy=False, attachment=True, help="Handwritten signature of the owner.")
    signed_by = fields.Char(string="Signed By", copy=False, tracking=True)
    signed_on = fields.Datetime(string="Signed On", copy=False, readonly=True)
    signed_ip = fields.Char(string="Signed From", copy=False, readonly=True)
    signature_hash = fields.Char(string="Fingerprint", copy=False, readonly=True,
                                 help="SHA-256 fingerprint of the text, the signature, the signer and the date.")
    revoke_reason = fields.Text(string="Reason", copy=False)

    def _compute_access_url(self):
        super()._compute_access_url()
        for consent in self:
            consent.access_url = f'/my/vet/consents/{consent.id}'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('vet.consent') or _("New")
        consents = super().create(vals_list)
        for consent in consents.filtered(lambda c: not c.content and c.template_id):
            consent.content = consent.template_id._render_body(consent.pet_id, consent.procedure, consent.vet_id)
        return consents

    def write(self, vals):
        if SIGNED_LOCKED_FIELDS & set(vals) and not self.env.context.get('vet_signing') \
                and any(c.state in ('signed', 'revoked') for c in self):
            raise UserError(_("A signed consent cannot be modified. Revoke it and prepare a new one."))
        return super().write(vals)

    def unlink(self):
        if any(c.state in ('signed', 'revoked') for c in self):
            raise UserError(_("Signed consents are part of the medical record and cannot be deleted."))
        return super().unlink()

    @api.onchange('template_id', 'pet_id', 'procedure')
    def _onchange_template_id(self):
        if self.template_id and self.pet_id and self.state == 'draft':
            self.content = self.template_id._render_body(self.pet_id, self.procedure, self.vet_id)

    def _get_signature_hash(self):
        self.ensure_one()
        digest = hashlib.sha256()
        for part in (self.name, str(self.content or ''), self.signed_by or '', fields.Datetime.to_string(self.signed_on) or ''):
            digest.update(part.encode())
        digest.update(base64.b64decode(self.signature or b''))
        return digest.hexdigest()

    def _sign(self, name, signature, ip=False):
        self.ensure_one()
        if self.state not in ('draft', 'sent'):
            raise UserError(_("This consent cannot be signed any more."))
        if not signature or not name:
            raise UserError(_("The signature and the name of the signer are required."))
        signer = self.with_context(vet_signing=True)
        signer.write({'signature': signature, 'signed_by': name, 'signed_on': fields.Datetime.now(),
                      'signed_ip': ip, 'state': 'signed'})
        signer.write({'signature_hash': self._get_signature_hash()})
        self.message_post(body=_("Consent signed by %s.", name))

    def action_sign(self):
        for consent in self:
            consent._sign(consent.signed_by or consent.owner_id.name, consent.signature)

    def action_send(self):
        for consent in self:
            if consent.state not in ('draft', 'sent'):
                raise UserError(_("Only draft consents can be sent for signature."))
            if not consent.owner_id.email:
                raise UserError(_("The owner %s has no email address.", consent.owner_id.name))
            consent._portal_ensure_token()
            url = consent.get_base_url() + consent.get_portal_url()
            consent.message_post(
                body=_("Please read and sign the consent %(title)s for %(pet)s: %(link)s", title=consent.title,
                       pet=consent.pet_id.name, link=Markup('<a href="%s">%s</a>') % (url, _("Open the consent"))),
                partner_ids=consent.owner_id.ids, message_type='comment', subtype_xmlid='mail.mt_comment')
            consent.state = 'sent'

    def action_refuse(self):
        self.filtered(lambda c: c.state in ('draft', 'sent')).write({'state': 'refused'})

    def action_revoke(self):
        for consent in self:
            if consent.state != 'signed':
                raise UserError(_("Only signed consents can be revoked."))
            if not consent.revoke_reason:
                raise UserError(_("Write the reason of the revocation first."))
            super(VetConsent, consent).write({'state': 'revoked'})
            consent.message_post(body=_("Consent revoked: %s", consent.revoke_reason))

    def action_verify_fingerprint(self):
        self.ensure_one()
        ok = self.state in ('signed', 'revoked') and self.signature_hash == self._get_signature_hash()
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'type': 'success' if ok else 'danger',
            'message': _("The signed document is intact.") if ok else _("The document does not match its fingerprint."),
        }}

    def action_print(self):
        return self.env.ref('odossey_veterinary.action_report_consent').report_action(self)

    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s - %s' % (self.name, self.title or '')


class VetPet(models.Model):
    _inherit = 'vet.pet'

    consent_ids = fields.One2many('vet.consent', 'pet_id')
