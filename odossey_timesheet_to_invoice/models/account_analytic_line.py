from odoo import _, api, fields, models
from odoo.exceptions import UserError

# timesheet fields changing the hours to invoice of a sales order line
SALE_QTY_FIELDS = {'to_invoice', 'unit_amount', 'so_line', 'task_id', 'project_id', 'product_uom_id'}


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    to_invoice = fields.Boolean(
        string="To Invoice",
        default=True,
        help="Untick for maintenance hours that must not be invoiced: they are left out "
             "of the quantity of the sales order line and reported as Extra Quantity.",
    )

    def _check_can_write(self, values):
        # same rule as the other billing fields: an invoiced timesheet is frozen
        if 'to_invoice' in values and self.sudo().filtered(
            lambda t: t.so_line.product_id.invoice_policy == 'delivery' and not t._is_not_billed()
        ):
            raise UserError(_('You cannot modify timesheets that are already invoiced.'))
        return super()._check_can_write(values)

    # The ordered quantity of the sales order lines is aligned right away (and not
    # only when the Extra Quantity is recomputed) so that it is up to date for the
    # rest of the transaction.

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.sudo().so_line._sync_qty_from_timesheets()
        return lines

    def write(self, vals):
        if not SALE_QTY_FIELDS.intersection(vals):
            return super().write(vals)
        so_lines = self.sudo().so_line
        res = super().write(vals)
        (so_lines | self.sudo().so_line)._sync_qty_from_timesheets()
        return res

    def unlink(self):
        so_lines = self.sudo().so_line
        res = super().unlink()
        so_lines._sync_qty_from_timesheets()
        return res
