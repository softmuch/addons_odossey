from collections import defaultdict

from odoo import api, fields, models
from odoo.fields import Domain


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    qty_extra = fields.Float(
        string="Extra Quantity",
        digits='Product Unit',
        compute='_compute_qty_extra',
        store=True,
        copy=False,
        help="Hours recorded on this line that are not to invoice (maintenance).",
    )

    def _get_timesheet_qty(self, to_invoice):
        """ Timesheet quantity linked to the lines, in the unit of each line.

        :param bool to_invoice: value of the To Invoice flag of the timesheets to sum
        :return: {sale order line id: quantity}, only for lines having such timesheets
        """
        result = defaultdict(float)
        line_ids = self._origin.ids
        if not line_ids:
            return result
        data = self.env['account.analytic.line'].sudo()._read_group(
            [('so_line', 'in', line_ids), ('project_id', '!=', False), ('to_invoice', '=', to_invoice)],
            ['product_uom_id', 'so_line'],
            ['unit_amount:sum'],
        )
        for uom, so_line, unit_amount in data:
            if uom and so_line.product_uom_id:
                unit_amount = uom._compute_quantity(unit_amount, so_line.product_uom_id, rounding_method='HALF-UP')
            result[so_line.id] += unit_amount
        return result

    @api.depends('analytic_line_ids.to_invoice', 'analytic_line_ids.unit_amount',
                 'analytic_line_ids.so_line', 'analytic_line_ids.project_id')
    def _compute_qty_extra(self):
        extra = self._get_timesheet_qty(to_invoice=False)
        for line in self:
            line.qty_extra = extra.get(line._origin.id, 0.0)
        # This compute runs each time a timesheet of the lines changes: keep the
        # ordered quantity aligned. It is not done by adding dependencies to
        # `_compute_product_uom_qty`, that would prevent its precomputation (and the
        # one of the prices). Existing orders are left untouched at install.
        if self.env.registry.ready:
            self._sync_qty_from_timesheets(extra)

    @api.depends('analytic_line_ids.to_invoice')
    def _compute_qty_delivered(self):
        super()._compute_qty_delivered()

    def _timesheet_compute_delivered_quantity_domain(self):
        domain = super()._timesheet_compute_delivered_quantity_domain()
        return Domain.AND([domain, [('to_invoice', '=', True)]])

    def _sync_qty_from_timesheets(self, extra=None):
        """ Set the ordered quantity of the lines having timesheets to their hours
        to invoice, when the company enabled it. """
        lines = self.filtered(lambda line: (
            line._origin.id
            and not line.display_type
            and line.company_id.timesheet_sync_sale_qty
            and line.state != 'cancel'
            and not line.order_id.locked
        ))
        if not lines:
            return
        to_invoice = lines._get_timesheet_qty(to_invoice=True)
        if extra is None:
            extra = lines._get_timesheet_qty(to_invoice=False)
        for line in lines:
            line_id = line._origin.id
            # lines without any timesheet keep the quantity typed by the user
            if line_id not in to_invoice and line_id not in extra:
                continue
            qty = to_invoice.get(line_id, 0.0)
            if line.product_uom_id.compare(line.product_uom_qty, qty) != 0:
                line.product_uom_qty = qty
