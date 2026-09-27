from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    trip_id = fields.Many2one(
        'travel.trip', string="Trip", index='btree_not_null', tracking=True, check_company=True,
        help="Trip of the invoice. On vendor bills, it links the supplier costs to the trip for "
             "the net profitability report.")
    travel_group_id = fields.Many2one(
        'travel.group', string="Travel Group", index='btree_not_null', check_company=True,
        domain="[('trip_id', '=', trip_id)]")

    @api.onchange('trip_id')
    def _onchange_trip_id_analytic(self):
        analytic = self.trip_id.analytic_account_id
        if not analytic:
            return
        for line in self.invoice_line_ids.filtered(lambda l: not l.analytic_distribution):
            line.analytic_distribution = {str(analytic.id): 100}
