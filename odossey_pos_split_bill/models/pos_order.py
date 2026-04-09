from odoo import api, models, fields
from odoo.addons.point_of_sale.models.pos_order import PosOrder

# In Odoo 18, pos.order inherits pos.load.mixin which exposes ALL fields
# to the JS frontend automatically. get_table_draft_orders, _order_fields
# and _export_for_ui no longer exist in Odoo 18.

class PosOrderV2(models.Model):
    _inherit = "pos.order"

    is_split = fields.Boolean("Is Split bill", default=False)
    to_split = fields.Integer("To Split", default=1)
    split_done = fields.Integer("Split Done", default=0)
    n_payments = fields.Integer("Nº Payments", default=1)

    def bill_made(self, order_id):
        order = self.browse(order_id)
        if order and order.is_split:
            res = order.write({"split_done": order.split_done + 1})
            return res

    @api.model
    def _process_order(self, order, existing_order):
        """Create or update an pos.order from a given dictionary.

        :param dict order: dictionary representing the order.
        :param existing_order: order to be updated or False.
        :type existing_order: pos.order.
        :returns: id of created/updated pos.order
        :rtype: int
        """
        draft = True if order.get('state') == 'draft' else False
        pos_session = self.env['pos.session'].browse(order['session_id'])
        if pos_session.state == 'closing_control' or pos_session.state == 'closed':
            order['session_id'] = self._get_valid_session(order).id

        if order.get('partner_id'):
            partner_id = self.env['res.partner'].browse(order['partner_id'])
            if not partner_id.exists():
                order.update({
                    "partner_id": False,
                    "to_invoice": False,
                })

        pos_order = False
        combo_child_uuids_by_parent_uuid = self._prepare_combo_line_uuids(order)

        if not existing_order:
            pos_order = self.create({
                **{key: value for key, value in order.items() if key != 'name'},'pos_reference': order.get('name')
            })
            pos_order = pos_order.with_company(pos_order.company_id)
        else:
            pos_order = self.env['pos.order'].browse(order.get('id'))

            # Avoid double updates (produce error on records deletion)
            lines_already_updated = False
            payments_already_updated = False

            # Save lines and payments before to avoid exception if a line is deleted
            # when vals change the state to 'paid'
            for field in ['lines', 'payment_ids']:
                if order.get(field): 
                    if field == 'payment_ids' and order.get(field):
                        if pos_order.is_split and pos_order.to_split > 1: 
                            for pay_list in order.get(field):
                                if pay_list and len(pay_list) == 3:
                                    pos_order.payment_ids.create(pay_list[2])
                            del order[field]
                        else:
                            payments_already_updated = True
                            pos_order.write({field: order.get(field)})
                    else:
                        lines_already_updated = True
                        pos_order.write({field: order.get(field)})

            # Remove lines and payments from order to avoid double updates
            if lines_already_updated:
                del order['lines']
            if payments_already_updated:
                del order['payment_ids']

            pos_order.write(order)

        pos_order._link_combo_items(combo_child_uuids_by_parent_uuid)
        self = self.with_company(pos_order.company_id)
        self._process_payment_lines(order, pos_order, pos_session, draft)
        return pos_order._process_saved_order(draft)


PosOrder._process_order = PosOrderV2._process_order