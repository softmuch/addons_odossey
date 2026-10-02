from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_report_timesheets(self):
        res = super()._get_report_timesheets()
        # Only a display value is stored: the invoice synchronization (taxes, terms,
        # balance check) is skipped so that nothing else is written, whatever the
        # state of the invoice.
        invoice_lines = self.sudo().invoice_line_ids.filtered('sale_line_ids').with_context(
            skip_invoice_sync=True,
            skip_invoice_line_sync=True,
            check_move_validity=False,
            skip_account_move_synchronization=True,
            tracking_disable=True,
        )
        # same printed hours as the quotation: they come from the sales order lines
        res['noise'] = invoice_lines.sale_line_ids._get_timesheet_noise()
        for line in invoice_lines:
            noise = {
                str(so_line.id): so_line.timesheet_noise
                for so_line in line.sale_line_ids if so_line.timesheet_noise
            } or False
            if noise != (line.timesheet_noise or False):
                line.timesheet_noise = noise
        return res
