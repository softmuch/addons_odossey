from dateutil.relativedelta import relativedelta
from werkzeug.exceptions import NotFound

from odoo import fields, http
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal


class RadioPortal(CustomerPortal):

    def _radio_contract_domain(self):
        partner = request.env.user.partner_id.commercial_partner_id
        return [('radio_contract', '=', True),
                '|', ('partner_id', 'child_of', partner.id),
                ('radio_agency_id', 'child_of', partner.id)]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'radio_contract_count' in counters:
            values['radio_contract_count'] = request.env['sale.subscription'].sudo().search_count(
                self._radio_contract_domain())
        return values

    def _radio_get_contract(self, contract_id):
        contract = request.env['sale.subscription'].sudo().search(
            self._radio_contract_domain() + [('id', '=', contract_id)], limit=1)
        if not contract:
            raise NotFound()
        return contract

    @http.route(['/my/radio'], type='http', auth='user', website=True)
    def portal_my_radio(self, **kw):
        contracts = request.env['sale.subscription'].sudo().search(
            self._radio_contract_domain(), order='date_start desc')
        values = self._prepare_portal_layout_values()
        values.update({'contracts': contracts, 'page_name': 'radio_contracts'})
        return request.render('odossey_radio.portal_my_radio', values)

    @http.route(['/my/radio/<int:contract_id>'], type='http', auth='user', website=True)
    def portal_my_radio_contract(self, contract_id, **kw):
        contract = self._radio_get_contract(contract_id)
        today = fields.Date.context_today(request.env.user)
        upcoming = contract.radio_emission_ids.filtered(
            lambda e: e.state == 'planned' and e.date >= today
        ).sorted(lambda e: (e.date, e.planned_time))[:50]
        aired = contract.radio_emission_ids.filtered(lambda e: e.state == 'aired')
        months = sorted({e.date.replace(day=1) for e in aired}, reverse=True)
        values = self._prepare_portal_layout_values()
        values.update({'contract': contract, 'upcoming': upcoming, 'months': months,
                       'aired_count': len(aired), 'page_name': 'radio_contract'})
        return request.render('odossey_radio.portal_my_radio_contract', values)

    @http.route(['/my/radio/<int:contract_id>/certificate/<string:month>'], type='http',
                auth='user', website=True)
    def portal_my_radio_certificate(self, contract_id, month, **kw):
        contract = self._radio_get_contract(contract_id)
        try:
            start = fields.Date.to_date(month).replace(day=1)
        except (TypeError, ValueError):
            raise NotFound()
        end = start + relativedelta(months=1, days=-1)
        pdf, __ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'odossey_radio.action_report_radio_certificate', contract.ids,
            data={'radio_date_from': fields.Date.to_string(start),
                  'radio_date_to': fields.Date.to_string(end)})
        filename = f"certificado-{contract.name}-{start.strftime('%Y-%m')}.pdf".replace('/', '-')
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'), ('Content-Length', len(pdf)),
            ('Content-Disposition', f'attachment; filename="{filename}"'),
        ])
