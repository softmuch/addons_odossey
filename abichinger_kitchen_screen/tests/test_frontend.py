import logging
import odoo.tests
from odoo.tests import loaded_demo_data
from odoo.addons.point_of_sale.tests.common import archive_products
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.base.tests.common import HttpCaseWithUserDemo

_logger = logging.getLogger(__name__)

@odoo.tests.tagged('post_install', '-at_install')
class TestFrontend(AccountTestInvoicingCommon, HttpCaseWithUserDemo):

    # CREDIT: odoo/addons/pos_restaurant/tests/test_frontend
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.user_demo.groups_id += cls.env.ref('point_of_sale.group_pos_manager') + cls.env.ref('account.group_account_invoice')

        user_admin = cls.env.ref('base.user_admin')
        (cls.user_demo + user_admin).write({
            'company_id': cls.env.company.id,
            'company_ids': [(4, cls.env.company.id)],
        })
        cls.env = cls.env(user=user_admin)
        archive_products(cls.env)
        account_obj = cls.env['account.account']

        account_receivable = account_obj.create({'code': 'X1012',
                                                 'name': 'Account Receivable - Test',
                                                 'account_type': 'asset_receivable',
                                                 'reconcile': True})

        drinks_category = cls.env['pos.category'].create({'name': 'Drinks'})

        printer = cls.env['pos.printer'].create({
            'name': 'Preparation Printer',
            'epson_printer_ip': '127.0.0.1',
            'printer_type': 'epson_epos',
            'product_categories_ids': [drinks_category.id]
        })

        main_company = cls.env.company

        cls.env['pos.payment.method'].create({
            'name': 'Bank',
            'journal_id': cls.company_data['default_journal_bank'].id,
            'receivable_account_id': cls.company_data['default_account_receivable'].id,
            'company_id': cls.env.company.id,
        })
        second_cash_journal = cls.env['account.journal'].create({
            'name': 'Cash 2',
            'type': 'cash',
            'company_id': main_company.id
        })

        cls.env['pos.payment.method'].create({
            'name': 'Cash 2',
            'split_transactions': False,
            'receivable_account_id': account_receivable.id,
            'journal_id': second_cash_journal.id,
        })

        pos_config = cls.env['pos.config'].create({
            'name': 'Bar Prout',
            'module_pos_restaurant': True,
            'iface_splitbill': True,
            'iface_printbill': True,
            'iface_orderline_notes': True,
            'iface_start_categ_id': drinks_category.id,
            'start_category': True,
            'is_order_printer': True,
            'printer_ids': [(4, printer.id)],
            'iface_tipproduct': False,
            'company_id': cls.env.company.id,
        })
        pos_config.floor_ids.unlink()

        main_floor = cls.env['restaurant.floor'].create({
            'name': 'Main Floor',
            'pos_config_ids': [(4, pos_config.id)],
        })

        cls.env['restaurant.table'].create({
            'name': '5',
            'floor_id': main_floor.id,
            'seats': 4,
            'position_h': 100,
            'position_v': 100,
        })
        cls.env['restaurant.table'].create({
            'name': '4',
            'floor_id': main_floor.id,
            'seats': 4,
            'shape': 'square',
            'position_h': 150,
            'position_v': 100,
        })
        cls.env['restaurant.table'].create({
            'name': '2',
            'floor_id': main_floor.id,
            'seats': 4,
            'position_h': 250,
            'position_v': 100,
        })

        second_floor = cls.env['restaurant.floor'].create({
            'name': 'Second Floor',
            'pos_config_ids': [(4, pos_config.id)],
        })

        cls.env['restaurant.table'].create({
            'name': '1',
            'floor_id': second_floor.id,
            'seats': 4,
            'shape': 'square',
            'position_h': 100,
            'position_v': 150,
        })
        cls.env['restaurant.table'].create({
            'name': '3',
            'floor_id': second_floor.id,
            'seats': 4,
            'position_h': 100,
            'position_v': 250,
        })

        cls.env['ir.property']._set_default(
            'property_account_receivable_id',
            'res.partner',
            account_receivable,
            main_company,
        )

        test_sale_journal = cls.env['account.journal'].create({
            'name': 'Sales Journal - Test',
            'code': 'TSJ',
            'type': 'sale',
            'company_id': main_company.id
            })

        cash_journal = cls.env['account.journal'].create({
            'name': 'Cash Test',
            'code': 'TCJ',
            'type': 'cash',
            'company_id': main_company.id
            })

        pos_config.write({
            'journal_id': test_sale_journal.id,
            'invoice_journal_id': test_sale_journal.id,
            'payment_method_ids': [(0, 0, {
                'name': 'Cash',
                'split_transactions': False,
                'receivable_account_id': account_receivable.id,
                'journal_id': cash_journal.id,
            })],
        })

        cls.env['product.product'].create({
            'available_in_pos': True,
            'list_price': 2.20,
            'name': 'Coca-Cola',
            'weight': 0.01,
            'pos_categ_ids': [(4, drinks_category.id)],
            'categ_id': cls.env.ref('point_of_sale.product_category_pos').id,
            'taxes_id': [(6, 0, [])],
        })

        cls.env['product.product'].create({
            'available_in_pos': True,
            'list_price': 2.20,
            'name': 'Water',
            'weight': 0.01,
            'pos_categ_ids': [(4, drinks_category.id)],
            'categ_id': cls.env.ref('point_of_sale.product_category_pos').id,
            'taxes_id': [(6, 0, [])],
        })

        cls.env['product.product'].create({
            'available_in_pos': True,
            'list_price': 2.20,
            'name': 'Minute Maid',
            'weight': 0.01,
            'pos_categ_ids': [(4, drinks_category.id)],
            'categ_id': cls.env.ref('point_of_sale.product_category_pos').id,
            'taxes_id': [(6, 0, [])],
        })

        #desk organizer (variant product)
        cls.desk_organizer = cls.env['product.product'].create({
            'name': 'Desk Organizer',
            'available_in_pos': True,
            'list_price': 5.10,
            'pos_categ_ids': [(4, drinks_category.id)], # will put it as a drink for convenience
        })
        desk_size_attribute = cls.env['product.attribute'].create({
            'name': 'Size',
            'display_type': 'radio',
            'create_variant': 'no_variant',
        })
        desk_size_s = cls.env['product.attribute.value'].create({
            'name': 'S',
            'attribute_id': desk_size_attribute.id,
        })
        desk_size_m = cls.env['product.attribute.value'].create({
            'name': 'M',
            'attribute_id': desk_size_attribute.id,
        })
        desk_size_l = cls.env['product.attribute.value'].create({
            'name': 'L',
            'attribute_id': desk_size_attribute.id,
        })
        cls.env['product.template.attribute.line'].create({
            'product_tmpl_id': cls.desk_organizer.product_tmpl_id.id,
            'attribute_id': desk_size_attribute.id,
            'value_ids': [(6, 0, [desk_size_s.id, desk_size_m.id, desk_size_l.id])]
        })
        desk_fabrics_attribute = cls.env['product.attribute'].create({
            'name': 'Fabric',
            'display_type': 'select',
            'create_variant': 'no_variant',
        })
        desk_fabrics_leather = cls.env['product.attribute.value'].create({
            'name': 'Leather',
            'attribute_id': desk_fabrics_attribute.id,
        })
        desk_fabrics_other = cls.env['product.attribute.value'].create({
            'name': 'Custom',
            'attribute_id': desk_fabrics_attribute.id,
            'is_custom': True,
        })
        cls.env['product.template.attribute.line'].create({
            'product_tmpl_id': cls.desk_organizer.product_tmpl_id.id,
            'attribute_id': desk_fabrics_attribute.id,
            'value_ids': [(6, 0, [desk_fabrics_leather.id, desk_fabrics_other.id])]
        })

        pricelist = cls.env['product.pricelist'].create({'name': 'Restaurant Pricelist'})
        pos_config.write({'pricelist_id': pricelist.id})

        cls.pos_config = pos_config

        cls.pos_admin = cls.env['res.users'].create({
            'name': 'A powerfull PoS man!',
            'login': 'pos_admin',
            'password': 'pos_admin',
            'groups_id': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref('point_of_sale.group_pos_manager').id),
            ],
        })
        cls.pos_admin.partner_id.email = 'pos_admin@test.com'

    def test_01_abichinger_kitchen_screen(self):
        if not loaded_demo_data(self.env):
            _logger.warning("This test relies on demo data. To be rewritten independently of demo data for accurate and reliable results.")
            return 
        
        _logger.info("Running test_01_abichinger_kitchen_screen")

        self.pos_config.with_user(self.pos_admin).open_ui()
        self.start_tour("/abichinger_kitchen_screen/app/?config_id=%d" % self.pos_config.id, 'abichinger_kitchen_screen_tour', login="pos_admin", watch=False)
        