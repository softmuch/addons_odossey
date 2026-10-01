from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_report_timesheets(self):
        """ Timesheets printed by the "Invoice + Hours" report, split by their
        To Invoice flag: the ones of the invoiced sales order lines that are linked
        to this invoice or not linked to any invoice (fixed price / ordered
        quantities services are never linked). """
        self.ensure_one()
        timesheets = self.env['account.analytic.line'].sudo().search([
            ('so_line', 'in', self.invoice_line_ids.sale_line_ids.ids),
            ('project_id', '!=', False),
            ('timesheet_invoice_id', 'in', [False, self.id]),
        ], order='date, id')
        invoiced = timesheets.filtered('to_invoice')
        return {'invoiced': invoiced, 'maintenance': timesheets - invoiced}
