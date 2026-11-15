from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestVetScope(TransactionCase):
    """Settings › Users › Veterinary › Scope: "Veterinary Only" shows only the Veterinary app."""

    def _apps(self, user):
        menus = self.env['ir.ui.menu'].with_user(user).load_menus(False)
        return {menus[i]['xmlid'] for i in menus['root']['children']}

    def _menu_ids(self, user):
        return set(self.env['ir.ui.menu'].with_user(user).load_menus(False)) - {'root'}

    def test_veterinary_only_hides_the_other_apps(self):
        groups = 'odossey_veterinary.group_vet_reception,point_of_sale.group_pos_user,purchase.group_purchase_user'
        all_apps = new_test_user(self.env, login='scope_all', groups=groups + ',odossey_veterinary.group_vet_scope_all')
        vet_only = new_test_user(self.env, login='scope_vet', groups=groups + ',odossey_veterinary.group_vet_scope_vet_only')
        self.assertIn('odossey_veterinary.menu_vet_root', self._apps(all_apps))
        self.assertGreater(len(self._apps(all_apps)), 1, "the reception rights also open other apps")
        self.assertEqual(self._apps(vet_only), {'odossey_veterinary.menu_vet_root'})
        # inside the app nothing is lost: same veterinary menus as a user with all the apps
        vet_menus = {self.env.ref(x).id for x in (
            'odossey_veterinary.menu_vet_agenda', 'odossey_veterinary.menu_vet_cash_desk',
            'odossey_veterinary.menu_vet_orders', 'odossey_veterinary.menu_vet_purchase_orders')}
        self.assertLessEqual(vet_menus, self._menu_ids(vet_only))
        root = self.env.ref('odossey_veterinary.menu_vet_root')
        vet_tree = {m.id for m in self.env['ir.ui.menu'].search([('parent_path', '=like', '%s/%%' % root.id)])}
        self.assertEqual(self._menu_ids(all_apps) & vet_tree, self._menu_ids(vet_only))

    def test_purchase_orders_from_the_veterinary_app(self):
        buyer = new_test_user(self.env, login='scope_buyer', groups='odossey_veterinary.group_vet_reception,'
                              'purchase.group_purchase_user,odossey_veterinary.group_vet_scope_vet_only')
        reception = new_test_user(self.env, login='scope_reception', groups='odossey_veterinary.group_vet_reception')
        menu = self.env.ref('odossey_veterinary.menu_vet_purchase_orders').id
        self.assertIn(menu, self._menu_ids(buyer))
        self.assertNotIn(menu, self._menu_ids(reception), "only users with the Purchase rights")
        supplier = self.env['res.partner'].create({'name': "Droguería Test"})
        product = self.env['product.product'].create({'name': "Vacuna test", 'type': 'consu'})
        order = self.env['purchase.order'].with_user(buyer).create({
            'partner_id': supplier.id, 'order_line': [(0, 0, {'product_id': product.id, 'product_qty': 3})]})
        self.assertEqual(order.state, 'draft')
        action = self.env.ref('odossey_veterinary.vet_purchase_order_action')
        self.assertFalse(action.domain, "drafts and confirmed orders, not only the confirmed ones")
