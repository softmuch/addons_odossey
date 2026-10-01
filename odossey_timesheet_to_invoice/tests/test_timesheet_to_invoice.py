from odoo.tests import tagged

from odoo.addons.sale_timesheet.tests.common import TestCommonSaleTimesheet


@tagged('post_install', '-at_install')
class TestTimesheetToInvoice(TestCommonSaleTimesheet):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.timesheet_sync_sale_qty = True
        cls.order = cls.env['sale.order'].create({'partner_id': cls.partner_a.id})
        cls.line_ordered, cls.line_delivered = cls.env['sale.order.line'].create([{
            'order_id': cls.order.id,
            'product_id': cls.product_order_timesheet3.id,
            'product_uom_qty': 10,
        }, {
            'order_id': cls.order.id,
            'product_id': cls.product_delivery_timesheet3.id,
            'product_uom_qty': 10,
        }])
        cls.order.action_confirm()

    def _log(self, line, hours, to_invoice=True):
        return self.env['account.analytic.line'].create({
            'name': 'work',
            'project_id': line.task_id.project_id.id,
            'task_id': line.task_id.id,
            'unit_amount': hours,
            'employee_id': self.employee_user.id,
            'to_invoice': to_invoice,
        })

    def test_default_to_invoice(self):
        timesheet = self.env['account.analytic.line'].create({
            'name': 'work',
            'project_id': self.line_ordered.task_id.project_id.id,
            'task_id': self.line_ordered.task_id.id,
            'unit_amount': 1,
            'employee_id': self.employee_user.id,
        })
        self.assertTrue(timesheet.to_invoice)

    def test_quantities_follow_flag(self):
        for line in (self.line_ordered, self.line_delivered):
            billable = self._log(line, 6.25)
            maintenance = self._log(line, 2.5, to_invoice=False)
            self.assertEqual(billable.so_line, line)
            self.assertEqual(line.product_uom_qty, 6.25)
            self.assertEqual(line.qty_extra, 2.5)
            self.assertEqual(line.qty_delivered, 6.25)

            maintenance.to_invoice = True
            self.assertEqual(line.product_uom_qty, 8.75)
            self.assertEqual(line.qty_extra, 0)
            self.assertEqual(line.qty_delivered, 8.75)

            billable.to_invoice = False
            self.assertEqual(line.product_uom_qty, 2.5)
            self.assertEqual(line.qty_extra, 6.25)

            billable.unlink()
            self.assertEqual(line.product_uom_qty, 2.5)
            self.assertEqual(line.qty_extra, 0)

    def test_sync_disabled(self):
        self.env.company.timesheet_sync_sale_qty = False
        self._log(self.line_ordered, 3)
        self._log(self.line_ordered, 1, to_invoice=False)
        self.assertEqual(self.line_ordered.product_uom_qty, 10, "the quantity must not be touched")
        self.assertEqual(self.line_ordered.qty_extra, 1)
        self.assertEqual(self.line_ordered.qty_delivered, 3)

    def test_invoice_and_reports(self):
        self._log(self.line_ordered, 4)
        self._log(self.line_ordered, 1.5, to_invoice=False)
        self._log(self.line_delivered, 2)
        self._log(self.line_delivered, 0.5, to_invoice=False)
        hours = self.order._get_report_timesheets()
        self.assertEqual(sum(hours['invoiced'].mapped('unit_amount')), 6)
        self.assertEqual(sum(hours['maintenance'].mapped('unit_amount')), 2)

        invoice = self.order._create_invoices()
        by_sol = {aml.sale_line_ids: aml for aml in invoice.invoice_line_ids}
        self.assertEqual(by_sol[self.line_ordered].quantity, 4)
        self.assertEqual(by_sol[self.line_ordered].qty_extra, 1.5)
        self.assertEqual(by_sol[self.line_delivered].quantity, 2)
        self.assertEqual(by_sol[self.line_delivered].qty_extra, 0.5)
        hours = invoice._get_report_timesheets()
        self.assertEqual(sum(hours['invoiced'].mapped('unit_amount')), 6)
        self.assertEqual(sum(hours['maintenance'].mapped('unit_amount')), 2)

        # the extra quantity is frozen once the invoice is posted
        invoice.action_post()
        self._log(self.line_ordered, 1, to_invoice=False)
        self.assertEqual(self.line_ordered.qty_extra, 2.5)
        self.assertEqual(by_sol[self.line_ordered].qty_extra, 1.5)

        for report, record in (
            ('odossey_timesheet_to_invoice.action_report_saleorder_hours', self.order),
            ('odossey_timesheet_to_invoice.action_report_invoice_hours', invoice),
        ):
            html = self.env['ir.actions.report']._render_qweb_html(report, record.ids)[0].decode()
            self.assertIn('hours_invoiced_title', html)
            self.assertIn('hours_maintenance_title', html)
        html = self.env['ir.actions.report']._render_qweb_html('sale.action_report_saleorder', self.order.ids)[0].decode()
        self.assertNotIn('hours_invoiced_title', html)
