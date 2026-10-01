from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_report_timesheets(self):
        res = super()._get_report_timesheets()
        res['noise'] = self.order_line._get_timesheet_noise()
        return res
