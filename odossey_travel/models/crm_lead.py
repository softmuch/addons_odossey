from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    trip_id = fields.Many2one('travel.trip', string="Trip", index='btree_not_null',
                              tracking=True, check_company=True)
    travel_pax_count = fields.Integer(string="Expected Passengers", default=1)
    travel_destination = fields.Char(
        string="Desired Destination",
        help="Destination requested by the customer when no trip is defined yet.")

    def _prepare_opportunity_quotation_context(self):
        context = super()._prepare_opportunity_quotation_context()
        if self.trip_id:
            context['default_trip_id'] = self.trip_id.id
        return context
