from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round


class OphPriceUpdate(models.TransientModel):
    _name = 'oph.price.update'
    _description = 'Update Agreed Fees'

    insurance_ids = fields.Many2many('oph.insurance', string="Health Insurances", required=True,
                                     default=lambda self: self.env.context.get('active_ids'))
    percentage = fields.Float(string="Increase (%)", required=True,
                              help="Percentage applied to the agreed fees. Example: 8 → a fee of 10,000 becomes 10,800. "
                                   "Use a negative value for a reduction.")
    update_copay = fields.Boolean(string="Update Co-payments Too", default=True)
    rounding = fields.Float(string="Round To", default=1.0, help="Example: 100 rounds 10,849 to 10,800.")

    def action_apply(self):
        self.ensure_one()
        if self.percentage <= -100:
            raise UserError(_("The reduction cannot be 100% or more."))
        factor = 1 + self.percentage / 100.0
        prices = self.insurance_ids.price_ids
        for price in prices:
            vals = {'insurance_amount': float_round(price.insurance_amount * factor, precision_rounding=self.rounding or 0.01)}
            if self.update_copay:
                vals['copay_amount'] = float_round(price.copay_amount * factor, precision_rounding=self.rounding or 0.01)
            price.write(vals)
        for insurance in self.insurance_ids:
            insurance.message_post(body=_("Agreed fees updated by %s%%.", self.percentage))
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'type': 'success', 'message': _("%s fees updated.", len(prices)),
            'next': {'type': 'ir.actions.act_window_close'}}}
