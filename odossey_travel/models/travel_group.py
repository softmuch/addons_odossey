from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class TravelGroup(models.Model):
    """Group of travellers of a trip.

    * family: one person (the leader) pays for everyone -> one booking / one invoice.
    * friends: every member pays his own share -> one booking and one invoice per member,
      all linked to the group so they can be filtered and grouped together.
    """
    _name = 'travel.group'
    _description = "Travel Group"
    _inherit = ['mail.thread']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(string="Group", required=True, tracking=True)
    trip_id = fields.Many2one('travel.trip', string="Trip", required=True, tracking=True,
                              check_company=True, index=True)
    company_id = fields.Many2one(related='trip_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='trip_id.currency_id')
    group_type = fields.Selection(
        selection=[('family', "Family (single payer)"), ('friends', "Friends (each one pays)")],
        string="Type", required=True, default='family', tracking=True)
    leader_id = fields.Many2one(
        'res.partner', string="Leader / Payer", required=True, tracking=True,
        help="For family groups, the person who pays and receives the invoice. For friends "
             "groups, the contact person of the group.")
    member_ids = fields.Many2many('res.partner', string="Members",
                                  help="Travellers of the group (include the leader if he "
                                       "travels too).")
    member_count = fields.Integer(compute='_compute_member_count', string="Members Count")
    sale_order_ids = fields.One2many('sale.order', 'travel_group_id', string="Bookings")
    order_count = fields.Integer(compute='_compute_totals', string="Bookings Count")
    invoice_count = fields.Integer(compute='_compute_totals', string="Invoices Count")
    amount_total = fields.Monetary(compute='_compute_totals', string="Total")
    amount_paid = fields.Monetary(compute='_compute_totals', string="Paid")
    amount_due = fields.Monetary(compute='_compute_totals', string="Balance")
    note = fields.Text(string="Notes")

    @api.depends('member_ids')
    def _compute_member_count(self):
        for group in self:
            group.member_count = len(group.member_ids)

    @api.depends('sale_order_ids.amount_total', 'sale_order_ids.travel_amount_paid',
                 'sale_order_ids.state')
    def _compute_totals(self):
        for group in self:
            orders = group.sale_order_ids.filtered(lambda o: o.state != 'cancel')
            group.order_count = len(group.sale_order_ids)
            group.invoice_count = self.env['account.move'].search_count(
                [('travel_group_id', '=', group.id)]) if group.id else 0
            group.amount_total = sum(orders.mapped('amount_total'))
            group.amount_paid = sum(orders.mapped('travel_amount_paid'))
            group.amount_due = group.amount_total - group.amount_paid

    @api.onchange('leader_id')
    def _onchange_leader_id(self):
        if self.leader_id and self.leader_id not in self.member_ids:
            self.member_ids = [Command.link(self.leader_id.id)]

    def action_create_bookings(self):
        """Create the missing quotations of the group according to its type."""
        SaleOrder = self.env['sale.order']
        created = SaleOrder
        for group in self:
            if not group.member_ids:
                raise UserError(self.env._("Add the members of the group first."))
            active_orders = group.sale_order_ids.filtered(lambda o: o.state != 'cancel')
            booked = active_orders.travel_passenger_ids.partner_id
            missing = group.member_ids - booked
            if not missing:
                continue
            common = {
                'trip_id': group.trip_id.id,
                'travel_group_id': group.id,
                'company_id': group.company_id.id,
            }
            if group.group_type == 'family':
                order = active_orders.filtered(
                    lambda o: o.partner_id == group.leader_id and o.state in ('draft', 'sent'))[:1]
                passenger_cmds = [Command.create({'partner_id': p.id}) for p in missing]
                if order:
                    order.travel_passenger_ids = passenger_cmds
                else:
                    order = SaleOrder.create(dict(common, partner_id=group.leader_id.id,
                                                  travel_passenger_ids=passenger_cmds))
                created |= order
            else:
                for member in missing:
                    created |= SaleOrder.create(dict(
                        common, partner_id=member.id,
                        travel_passenger_ids=[Command.create({'partner_id': member.id})]))
        created._travel_load_services()
        return self.action_view_orders()

    def action_view_orders(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_travel.travel_booking_action')
        action['domain'] = [('travel_group_id', 'in', self.ids)]
        if len(self) == 1:
            action['context'] = {'default_travel_group_id': self.id,
                                 'default_trip_id': self.trip_id.id}
        return action

    def action_create_invoices(self):
        """Invoice the group: one invoice for a family, one per member for friends."""
        orders = self.sale_order_ids.filtered(
            lambda o: o.state == 'sale' and o.invoice_status == 'to invoice')
        if not orders:
            raise UserError(self.env._(
                "There is nothing to invoice. Confirm the bookings of the group first."))
        # grouped=True: never merge the bookings of different members in one invoice
        orders._create_invoices(grouped=True, final=True)
        return self.action_view_invoices()

    def action_view_invoices(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odossey_travel.travel_invoice_action')
        action['domain'] = [('travel_group_id', 'in', self.ids)]
        action['context'] = {'search_default_group_by_group': 1}
        return action
