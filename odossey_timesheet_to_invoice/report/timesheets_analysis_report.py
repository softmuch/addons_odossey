from odoo import fields, models


class TimesheetsAnalysisReport(models.Model):
    _inherit = 'timesheets.analysis.report'

    to_invoice = fields.Boolean(string="To Invoice", readonly=True)

    def _select(self):
        return super()._select() + """,
            A.to_invoice AS to_invoice
        """
