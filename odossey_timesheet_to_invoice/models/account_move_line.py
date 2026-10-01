from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    qty_extra = fields.Float(
        string="Extra Quantity",
        digits='Product Unit',
        compute='_compute_qty_extra',
        store=True,
        copy=False,
        help="Hours recorded on the invoiced sales order lines that are not to "
             "invoice (maintenance).",
    )

    @api.depends('sale_line_ids.qty_extra', 'product_uom_id', 'parent_state')
    def _compute_qty_extra(self):
        # the value is frozen once the invoice leaves the draft state, except while
        # installing the module (existing invoices get their value)
        freeze = self.env.registry.ready
        for line in self:
            if freeze and line.parent_state != 'draft':
                continue
            qty_extra = 0.0
            if line.display_type == 'product' and line.move_id.move_type == 'out_invoice':
                for so_line in line.sale_line_ids:
                    # extra hours already reported by other posted invoices of the line
                    reported = sum((so_line.invoice_lines - line).filtered(
                        lambda aml: aml.parent_state == 'posted' and aml.move_id.move_type == 'out_invoice'
                    ).mapped('qty_extra'))
                    qty = max(so_line.qty_extra - reported, 0.0)
                    if so_line.product_uom_id and line.product_uom_id:
                        qty = so_line.product_uom_id._compute_quantity(
                            qty, line.product_uom_id, rounding_method='HALF-UP')
                    qty_extra += qty
            line.qty_extra = qty_extra
