import uuid
from unittest.mock import patch

from odoo import fields
from odoo.tests import new_test_user, tagged

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged('post_install', '-at_install')
class TestVetCashDesk(TestPointOfSaleHttpCommon):
    """Orders of the visits charged at the Point of Sale: payment status, live list of the tills, single delivery."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(su=True)  # the common runs as a till user; data of the clinic is set up as superuser
        cls.vet_owner = cls.env['res.partner'].create({'name': "Marta Gómez", 'phone': '351 555 1234'})
        cls.vet_pet = cls.env['vet.pet'].create({
            'name': "Toby", 'owner_id': cls.vet_owner.id,
            'species_id': cls.env.ref('odossey_veterinary.species_dog').id,
        })
        cls.vet_service = cls.env['product.product'].create({
            'name': "Consulta test", 'type': 'service', 'list_price': 100.0, 'taxes_id': [(6, 0, [])],
            'available_in_pos': True,
        })
        cls.vet_med = cls.env['product.product'].create({
            'name': "Comprimido test", 'is_storable': True, 'list_price': 50.0, 'taxes_id': [(6, 0, [])],
            'available_in_pos': True,
        })
        cls.env['stock.quant']._update_available_quantity(
            cls.vet_med, cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1).lot_stock_id, 10)
        cls.main_pos_config.open_ui()
        cls.session = cls.main_pos_config.current_session_id

    def _vet_order(self, confirm=True):
        order = self.env['sale.order'].create({
            'partner_id': self.vet_owner.id, 'vet_pet_id': self.vet_pet.id,
            'order_line': [(0, 0, {'product_id': self.vet_service.id, 'product_uom_qty': 1, 'price_unit': 100.0, 'tax_ids': []}),
                           (0, 0, {'product_id': self.vet_med.id, 'product_uom_qty': 2, 'price_unit': 50.0, 'tax_ids': []})],
        })
        if confirm:
            order.action_confirm()
        return order

    def _pos_payload(self, order, amount=None, state='paid', lines=None, to_invoice=False):
        lines = lines or order.order_line
        total = amount if amount is not None else sum(l.price_total for l in lines)
        return {
            'amount_paid': total if state == 'paid' else 0, 'amount_return': 0, 'amount_tax': 0, 'amount_total': total,
            'date_order': fields.Datetime.to_string(fields.Datetime.now()),
            'fiscal_position_id': False, 'to_invoice': to_invoice, 'partner_id': order.partner_id.id,
            'pricelist_id': self.main_pos_config.available_pricelist_ids[:1].id,
            'lines': [[0, 0, {
                'discount': 0, 'pack_lot_ids': [], 'price_unit': l.price_unit, 'product_id': l.product_id.id,
                'price_subtotal': l.price_total, 'price_subtotal_incl': l.price_total, 'tax_ids': [],
                'sale_order_line_id': l.id, 'sale_order_origin_id': order.id, 'qty': l.product_uom_qty,
            }] for l in lines],
            'session_id': self.session.id,
            'payment_ids': [[0, 0, {
                'amount': total, 'name': fields.Datetime.now(),
                'payment_method_id': self.main_pos_config.payment_method_ids[0].id,
            }]] if state == 'paid' else [],
            'uuid': str(uuid.uuid4()), 'state': state, 'user_id': self.env.uid,
        }

    def _till_list(self, search=None):
        return self.env['sale.order'].vet_pos_search_orders(self.main_pos_config.id, search)

    def test_new_order_is_listed_until_paid(self):
        order = self._vet_order()
        self.assertTrue(order.vet_chargeable)
        self.assertEqual(order.vet_payment_state, 'unpaid')
        self.assertEqual(order.vet_amount_due, 200.0)
        listed = self._till_list()
        self.assertEqual(listed[0]['id'], order.id, "newest order first")
        self.assertEqual(listed[0]['pet'], "Toby")
        self.assertIn(order.id, [o['id'] for o in self._till_list("toby")])
        self.assertIn(order.id, [o['id'] for o in self._till_list("555 1234")])
        self.assertNotIn(order.id, [o['id'] for o in self._till_list("firulais")])
        count = self.env['sale.order'].vet_pos_count_orders(self.main_pos_config.id)

        self.env['pos.order'].sync_from_ui([self._pos_payload(order)])
        self.assertEqual(order.vet_payment_state, 'paid')
        self.assertEqual(order.vet_amount_due, 0.0)
        self.assertNotIn(order.id, [o['id'] for o in self._till_list()])
        self.assertEqual(self.env['sale.order'].vet_pos_count_orders(self.main_pos_config.id), count - 1)

    def test_stock_leaves_once(self):
        order = self._vet_order()
        stock = self.vet_med.qty_available
        self.env['pos.order'].sync_from_ui([self._pos_payload(order)])
        self.assertEqual(self.vet_med.qty_available, stock - 2, "the till delivers, the delivery of the order does not")
        self.assertTrue(all(p.state == 'cancel' for p in order.picking_ids))

    def test_open_till_keeps_the_order_listed(self):
        """An order loaded in a till but not paid (draft) stays in the list, 'At the Cash Desk'."""
        order = self._vet_order()
        self.env['pos.order'].sync_from_ui([self._pos_payload(order, state='draft')])
        self.assertEqual(order.vet_payment_state, 'in_pos')
        self.assertEqual(order.vet_amount_due, 200.0)
        self.assertIn(order.id, [o['id'] for o in self._till_list()])

    def test_partial_payment(self):
        order = self._vet_order()
        self.env['pos.order'].sync_from_ui([self._pos_payload(order, lines=order.order_line[:1])])
        self.assertEqual(order.vet_payment_state, 'partial')
        self.assertEqual(order.vet_amount_due, 100.0)
        self.assertIn(order.id, [o['id'] for o in self._till_list()])

    def test_invoiced_at_the_till(self):
        order = self._vet_order()
        self.env['pos.order'].sync_from_ui([self._pos_payload(order, to_invoice=True)])
        self.assertEqual(order.vet_payment_state, 'invoiced')

    def test_draft_quotation_and_cancel(self):
        order = self._vet_order(confirm=False)
        self.assertEqual(order.vet_payment_state, 'unpaid', "a quotation of a visit can also be charged")
        order._action_cancel()
        self.assertFalse(order.vet_payment_state)
        self.assertNotIn(order.id, [o['id'] for o in self._till_list()])

    def test_not_veterinary_order(self):
        order = self.env['sale.order'].create({
            'partner_id': self.vet_owner.id,
            'order_line': [(0, 0, {'product_id': self.vet_service.id, 'product_uom_qty': 1})],
        })
        self.assertFalse(order.vet_chargeable)
        self.assertFalse(order.vet_payment_state)

    def test_open_tills_are_notified(self):
        PosConfig = self.env.registry['pos.config']
        with patch.object(PosConfig, '_notify', autospec=True) as notify:
            self._vet_order()
            self.env.cr.precommit.run()
        names = [call.args[1] for call in notify.call_args_list]
        self.assertEqual(names.count('VET_ORDERS_CHANGED'), 1, "one notification per transaction and open till")
        self.assertEqual(notify.call_args_list[0].args[0], self.main_pos_config)

        with patch.object(PosConfig, '_notify', autospec=True) as notify:
            self.env['sale.order'].create({'partner_id': self.vet_owner.id})
            self.env.cr.precommit.run()
        self.assertFalse(notify.called, "orders that are not of a patient do not bother the tills")

    def test_reception_sees_orders_of_every_veterinarian(self):
        vet = new_test_user(self.env, login='vet_cash', groups='odossey_veterinary.group_vet_veterinarian')
        reception = new_test_user(self.env, login='reception_cash',
                                    groups='odossey_veterinary.group_vet_reception,point_of_sale.group_pos_user')
        order = self._vet_order()
        order.user_id = vet
        listed = self.env['sale.order'].with_user(reception).vet_pos_search_orders(self.main_pos_config.id)
        self.assertIn(order.id, [o['id'] for o in listed])
