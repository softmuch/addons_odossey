from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

DOCUMENT_REPORTS = {
    'glasses': ('oph.glasses.prescription', 'odossey_ophthalmology.action_report_glasses', ('issued',)),
    'prescriptions': ('oph.prescription', 'odossey_ophthalmology.action_report_prescription', ('issued',)),
    'studies': ('oph.study', 'odossey_ophthalmology.action_report_study', ('reported',)),
    'certificates': ('oph.certificate', 'odossey_ophthalmology.action_report_certificate', ('issued',)),
    'surgeries': ('oph.surgery', 'odossey_ophthalmology.action_report_implant_card', ('done',)),
}


class OphPortal(CustomerPortal):

    def _oph_patients(self):
        """The logged-in patient and the patients of his company (e.g. children registered under a parent)."""
        partner = request.env.user.partner_id
        return request.env['res.partner'].sudo().search([
            ('is_oph_patient', '=', True), ('id', 'child_of', partner.commercial_partner_id.id)])

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'oph_document_count' in counters:
            patients = self._oph_patients()
            values['oph_document_count'] = len(patients.oph_glasses_ids.filtered(lambda r: r.state == 'issued')) \
                + len(patients.oph_prescription_ids.filtered(lambda r: r.state == 'issued')) \
                + len(patients.oph_study_ids.filtered(lambda r: r.state == 'reported')) \
                + len(patients.oph_certificate_ids.filtered(lambda r: r.state == 'issued')) \
                + len(patients.oph_consent_ids.filtered(lambda r: r.state in ('sent', 'signed')))
        return values

    @http.route(['/my/ophthalmology'], type='http', auth='user', website=True)
    def portal_my_ophthalmology(self, **kw):
        patients = self._oph_patients()
        now = fields.Datetime.now()
        return request.render('odossey_ophthalmology.portal_my_ophthalmology', {
            'page_name': 'oph_home',
            'patients': patients,
            'appointments': patients.oph_appointment_ids.filtered(
                lambda e: e.start and e.start >= now and e.oph_state not in ('cancelled', 'no_show', 'withdrawn')).sorted('start'),
            'glasses': patients.oph_glasses_ids.filtered(lambda r: r.state == 'issued').sorted('date', reverse=True),
            'prescriptions': patients.oph_prescription_ids.filtered(lambda r: r.state == 'issued').sorted('date', reverse=True),
            'studies': patients.oph_study_ids.filtered(lambda r: r.state == 'reported').sorted('date', reverse=True),
            'certificates': patients.oph_certificate_ids.filtered(lambda r: r.state == 'issued').sorted('date', reverse=True),
            'consents': patients.oph_consent_ids.filtered(lambda r: r.state in ('sent', 'signed')),
            'surgeries': patients.oph_surgery_ids.filtered(lambda r: r.state != 'cancel').sorted('start', reverse=True),
        })

    @http.route(['/my/ophthalmology/<string:kind>/<int:record_id>'], type='http', auth='public', website=True)
    def portal_oph_document(self, kind, record_id, access_token=None, download=False, **kw):
        if kind not in DOCUMENT_REPORTS:
            return request.redirect('/my')
        model, report_ref, states = DOCUMENT_REPORTS[kind]
        try:
            record = self._document_check_access(model, record_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        if record.state not in states:
            return request.redirect('/my')
        return self._show_report(model=record, report_type='pdf', report_ref=report_ref, download=download)

    @http.route(['/my/ophthalmology/consents/<int:consent_id>'], type='http', auth='public', website=True)
    def portal_consent(self, consent_id, access_token=None, report_type=None, download=False, message=None, **kw):
        try:
            consent = self._document_check_access('oph.consent', consent_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(model=consent, report_type=report_type,
                                     report_ref='odossey_ophthalmology.action_report_consent', download=download)
        return request.render('odossey_ophthalmology.portal_consent_page', {
            'consent': consent, 'page_name': 'oph_consent', 'message': message,
            'can_sign': consent.state in ('draft', 'sent'),
        })

    @http.route(['/my/ophthalmology/consents/<int:consent_id>/sign'], type='jsonrpc', auth='public', website=True)
    def portal_consent_sign(self, consent_id, access_token=None, name=None, signature=None):
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            consent = self._document_check_access('oph.consent', consent_id, access_token=access_token)
        except (AccessError, MissingError):
            return {'error': _("Invalid consent.")}
        try:
            consent._sign(name, signature, ip=request.httprequest.remote_addr)
        except UserError as error:
            return {'error': str(error)}
        return {'force_refresh': True, 'redirect_url': consent.get_portal_url(query_string='&message=sign_ok')}
