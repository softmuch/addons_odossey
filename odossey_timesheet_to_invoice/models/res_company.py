from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    timesheet_sync_sale_qty = fields.Boolean(
        string="Quantity From Hours To Invoice",
        default=True,
        help="When enabled, the Quantity of a sales order line that has timesheets "
             "is kept equal to the hours marked 'To Invoice'. The hours that are not "
             "to invoice go to the Extra Quantity column.\n"
             "Example: 8.75 h recorded, 2.50 h unticked -> Quantity 6.25, Extra Quantity 2.50.\n"
             "When disabled, the Quantity is never touched (useful for prepaid hour "
             "packs); only Delivered and Extra Quantity follow the timesheets.",
    )
