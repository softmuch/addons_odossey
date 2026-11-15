import math

from odoo import _, api, fields, models
from odoo.fields import Domain

VET_PENDING_STATES = ('unpaid', 'in_pos', 'partial')
VET_POS_NOTIFICATION = 'VET_ORDERS_CHANGED'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    vet_chargeable = fields.Boolean(
        string="Veterinary Order", compute='_compute_vet_chargeable', store=True, index=True,
        help="Order of a patient (consultation, adjustment, hospitalization): the reception charges it at the cash desk.")
    vet_amount_due = fields.Monetary(
        string="To Charge", compute='_compute_vet_payment', store=True,
        help="Total of the order minus what was already paid at the cash desk or invoiced from the order.")
    vet_payment_state = fields.Selection([
        ('unpaid', "Not Paid"),
        ('in_pos', "At the Cash Desk"),
        ('partial', "Partially Paid"),
        ('paid', "Paid"),
        ('invoiced', "Invoiced"),
    ], string="Payment", compute='_compute_vet_payment', store=True, index=True,
        help="Not Paid: nobody charged it yet. At the Cash Desk: loaded in a till but not paid yet. "
             "Paid: charged at the cash desk with a ticket. Invoiced: charged with an invoice.")
    vet_veterinarian_id = fields.Many2one(
        'res.users', string="Veterinarian", compute='_compute_vet_veterinarian_id', store=True)

    @api.depends('vet_pet_id', 'vet_consultation_id')
    def _compute_vet_chargeable(self):
        for order in self:
            order.vet_chargeable = bool(order.vet_pet_id or order.vet_consultation_id)

    @api.depends('vet_consultation_id.vet_id', 'user_id')
    def _compute_vet_veterinarian_id(self):
        for order in self:
            vet = order.vet_consultation_id.vet_id
            if not vet and order.user_id.vet_is_veterinarian:
                vet = order.user_id
            order.vet_veterinarian_id = vet

    @api.depends('state', 'amount_total', 'amount_paid', 'vet_chargeable',
                 'order_line.pos_order_line_ids.order_id.state',
                 'order_line.pos_order_line_ids.order_id.account_move',
                 'order_line.pos_order_line_ids.price_subtotal_incl',
                 'order_line.invoice_lines.parent_state', 'order_line.invoice_lines.price_total')
    def _compute_vet_payment(self):
        """Same arithmetic as the core "Amount To Pay In POS", but a till left open with the order (draft) does not
        count as paid and cancelled tills are ignored."""
        for order in self:
            if not order.vet_chargeable or order.state == 'cancel':
                order.vet_amount_due = 0.0
                order.vet_payment_state = False
                continue
            sudo_order = order.sudo()
            pos_lines = sudo_order.order_line.filtered(lambda l: not l.display_type).pos_order_line_ids
            paid_lines = pos_lines.filtered(lambda l: l.order_id.state not in ('draft', 'cancel'))
            pos_paid = sum(-l.price_subtotal_incl if l.order_id.is_refund else l.price_subtotal_incl for l in paid_lines)
            invoice_lines = sudo_order.order_line.invoice_lines.filtered(lambda l: l.parent_state in ('draft', 'posted'))
            invoiced = sum(math.copysign(l.price_total, -l.balance) for l in invoice_lines)
            currency = order.currency_id
            due = max(order.amount_total - pos_paid - invoiced - order.amount_paid, 0.0)
            due = 0.0 if currency.is_zero(due) else currency.round(due)
            order.vet_amount_due = due
            if due:
                if pos_lines.filtered(lambda l: l.order_id.state == 'draft'):
                    state = 'in_pos'
                elif not currency.is_zero(pos_paid + invoiced + order.amount_paid):
                    state = 'partial'
                else:
                    state = 'unpaid'
            else:
                pos_orders = paid_lines.order_id
                with_invoice = invoice_lines.filtered(lambda l: l.parent_state == 'posted') or (
                    pos_orders and all(o.account_move.state == 'posted' for o in pos_orders))
                state = 'invoiced' if with_invoice else 'paid'
            order.vet_payment_state = state

    # ------------------------------------------------------------------ cash desk (Point of Sale)
    @api.model
    def _vet_pos_domain(self, config, search=None):
        domain = Domain([
            ('vet_chargeable', '=', True), ('state', '!=', 'cancel'),
            ('vet_payment_state', 'in', VET_PENDING_STATES),
            ('company_id', '=', config.company_id.id), ('currency_id', '=', config.currency_id.id),
        ])
        for word in (search or '').split():
            domain &= Domain('name', 'ilike', word) | Domain('vet_pet_id.name', 'ilike', word) \
                | Domain('partner_id', 'ilike', word) | Domain('partner_id.phone', 'ilike', word) \
                | Domain('partner_id.vat', 'ilike', word)
        return domain

    @api.model
    def vet_pos_search_orders(self, config_id, search=None, limit=80):
        """Orders the reception charges at the cash desk: veterinary orders not paid yet, newest first."""
        config = self.env['pos.config'].browse(config_id)
        orders = self.search(self._vet_pos_domain(config, search), order='date_order desc, id desc', limit=limit)
        labels = dict(self._fields['vet_payment_state']._description_selection(self.env))
        return [{
            'id': order.id,
            'name': order.name,
            'date': fields.Datetime.to_string(order.date_order),
            'pet': order.vet_pet_id.name or '',
            'owner': order.partner_id.name or '',
            'phone': order.partner_id.phone or '',
            'veterinarian': order.vet_veterinarian_id.name or '',
            'amount_total': order.amount_total,
            'amount_due': order.vet_amount_due,
            'payment_state': order.vet_payment_state,
            'payment_state_label': labels.get(order.vet_payment_state, ''),
        } for order in orders]

    @api.model
    def vet_pos_count_orders(self, config_id):
        config = self.env['pos.config'].browse(config_id)
        return self.search_count(self._vet_pos_domain(config))

    # ------------------------------------------------------------------ live refresh of the open tills
    def _vet_notify_pos(self):
        """Tell the open tills that the list of veterinary orders to charge changed (sent on commit, once)."""
        if not self.filtered('vet_chargeable') or self.env.context.get('vet_no_pos_notify'):
            return
        data = self.env.cr.precommit.data
        if data.get('odossey_veterinary.pos_notify'):
            return
        data['odossey_veterinary.pos_notify'] = True
        env = self.env

        @env.cr.precommit.add
        def _notify_open_tills():
            data.pop('odossey_veterinary.pos_notify', None)
            sessions = env['pos.session'].sudo().search([('state', 'in', ('opening_control', 'opened'))])
            for config in sessions.config_id:
                config._notify(VET_POS_NOTIFICATION, {})

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._vet_notify_pos()
        return orders

    def write(self, vals):
        res = super().write(vals)
        self._vet_notify_pos()
        return res

    def _action_confirm(self):
        res = super()._action_confirm()
        self._vet_notify_pos()
        return res

    def _action_cancel(self):
        res = super()._action_cancel()
        self._vet_notify_pos()
        return res

    def action_vet_view_pos_orders(self):
        self.ensure_one()
        return self.sudo().action_view_pos_order()


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def sync_from_ui(self, orders):
        res = super().sync_from_ui(orders)
        sale_orders = self.env['sale.order']
        ids = [o['id'] for o in res.get('pos.order', [])]
        if ids:
            sale_orders = self.browse(ids).sudo().lines.sale_order_origin_id
        sale_orders._vet_notify_pos()
        return res

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals or 'account_move' in vals:
            self.sudo().lines.sale_order_origin_id._vet_notify_pos()
        return res


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        self.sudo().line_ids.sale_line_ids.order_id._vet_notify_pos()
        return res
