from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    vet_pet_ids = fields.One2many('vet.pet', 'owner_id', string="Pets")
    vet_pet_count = fields.Integer(string="Number of Pets", compute='_compute_vet_pet_count')
    is_pet_owner = fields.Boolean(compute='_compute_vet_pet_count', search='_search_is_pet_owner')

    @api.depends('vet_pet_ids')
    def _compute_vet_pet_count(self):
        data = dict(self.env['vet.pet']._read_group([('owner_id', 'in', self.ids)], ['owner_id'], ['__count']))
        for partner in self:
            partner.vet_pet_count = data.get(partner, 0) if partner.id else len(partner.vet_pet_ids)
            partner.is_pet_owner = bool(partner.vet_pet_count)

    def _search_is_pet_owner(self, operator, value):
        owners = self.env['vet.pet'].with_context(active_test=False)._read_group([], ['owner_id'])
        ids = [o.id for (o,) in owners]
        values = [value] if isinstance(value, bool) or value is None else list(value)
        wants_owner = True in values
        positive = wants_owner if operator in ('=', 'in') else not wants_owner
        return [('id', 'in' if positive else 'not in', ids)]

    def action_vet_view_pets(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('odossey_veterinary.vet_pet_action')
        action['domain'] = [('owner_id', '=', self.id)]
        action['context'] = {'default_owner_id': self.id}
        return action
