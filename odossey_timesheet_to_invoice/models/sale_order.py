from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_report_timesheets(self):
        """ Timesheets printed by the "PDF Quote + Hours" report, split by their
        To Invoice flag. """
        self.ensure_one()
        timesheets = self.env['account.analytic.line'].sudo().search([
            ('so_line', 'in', self.order_line.ids),
            ('project_id', '!=', False),
        ], order='date, id')
        invoiced = timesheets.filtered('to_invoice')
        return {'invoiced': invoiced, 'maintenance': timesheets - invoiced}
