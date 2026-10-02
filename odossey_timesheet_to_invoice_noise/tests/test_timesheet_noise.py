import re

from odoo.tests import tagged

from odoo.addons.sale_timesheet.tests.common import TestCommonSaleTimesheet


@tagged('post_install', '-at_install')
class TestTimesheetNoise(TestCommonSaleTimesheet):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.timesheet_sync_sale_qty = True
        cls.env.company.timesheet_noise_minutes = 5
        cls.order = cls.env['sale.order'].create({'partner_id': cls.partner_a.id})
        cls.line = cls.env['sale.order.line'].create({
            'order_id': cls.order.id,
            'product_id': cls.product_order_timesheet3.id,
            'product_uom_qty': 10,
        })
        cls.order.action_confirm()
        cls.timesheets = cls.env['account.analytic.line']
        for hours, to_invoice in ((0.5, True), (0.25, True), (1, True), (0.75, True), (0.5, False), (0.25, False)):
            cls.timesheets |= cls._log(hours, to_invoice)

    @classmethod
    def _log(cls, hours, to_invoice=True):
        return cls.env['account.analytic.line'].create({
            'name': 'work',
            'project_id': cls.line.task_id.project_id.id,
            'task_id': cls.line.task_id.id,
            'unit_amount': hours,
            'employee_id': cls.employee_user.id,
            'to_invoice': to_invoice,
        })

    def _snapshot(self):
        self.env.flush_all()
        self.env.invalidate_all()
        return (
            self.order.amount_untaxed, self.order.amount_total,
            self.line.product_uom_qty, self.line.qty_extra, self.line.qty_delivered,
            self.line.price_unit, self.line.price_subtotal,
            self.timesheets.mapped('unit_amount'),
        )

    def test_generator(self):
        generate = self.env['sale.order.line']._generate_timesheet_noise
        for amounts in ([0.5], [0.5, 0.25], [0.25] * 51, [0.05, 0.05, 0.5], [0.02, 0.02], [0, 0.5, 0.5]):
            for max_minutes in (5, 1, 0):
                for _i in range(50):
                    deltas = generate(amounts, max_minutes)
                    self.assertEqual(len(deltas), len(amounts))
                    self.assertEqual(sum(deltas), 0)
                    self.assertTrue(all(abs(delta) <= max_minutes for delta in deltas))
                    self.assertTrue(all(not delta or amount * 60 + delta >= 1 for amount, delta in zip(amounts, deltas)))
        self.assertTrue(any(generate([0.5, 0.25, 1], 5)))
        # durations that are not a whole number of minutes are not varied
        self.assertEqual(generate([0.125, 0.5, 0.5], 5)[0], 0)
        self.assertFalse(any(generate([0.125, 0.375], 5)))

    def test_printed_hours(self):
        before = self._snapshot()
        hours = self.order._get_report_timesheets()
        noise = hours['noise']
        self.assertEqual(set(noise), set(self.timesheets.ids))
        for key in ('invoiced', 'maintenance'):
            timesheets = hours[key]
            self.assertAlmostEqual(
                sum(noise[timesheet.id] for timesheet in timesheets),
                sum(timesheets.mapped('unit_amount')),
                msg="the printed hours of a section add up to the recorded ones")
            for timesheet in timesheets:
                self.assertLessEqual(abs(noise[timesheet.id] - timesheet.unit_amount) * 60, 5 + 1e-6)
        self.assertTrue(any(abs(noise[t.id] - t.unit_amount) > 1e-6 for t in self.timesheets))
        self.assertTrue(self.line.timesheet_noise)
        self.assertEqual(self._snapshot(), before, "amounts, quantities and timesheets are untouched")

        # printing again gives the same hours
        self.assertEqual(self.order._get_report_timesheets()['noise'], noise)

        # a new timesheet only regenerates its own group
        maintenance = hours['maintenance']
        self._log(0.5)
        new_noise = self.order._get_report_timesheets()['noise']
        for timesheet in maintenance:
            self.assertEqual(new_noise[timesheet.id], noise[timesheet.id])

    def test_invoice(self):
        noise = self.order._get_report_timesheets()['noise']
        invoice = self.order._create_invoices()
        invoice_line = invoice.invoice_line_ids
        self.assertEqual(invoice_line.timesheet_noise, {str(self.line.id): self.line.timesheet_noise})
        amounts = (invoice.amount_untaxed, invoice.amount_total, invoice_line.quantity, invoice_line.price_subtotal)
        invoice.action_post()
        write_date = invoice.write_date
        invoice_line.timesheet_noise = False
        self.assertEqual(invoice._get_report_timesheets()['noise'], noise)
        self.assertEqual(invoice_line.timesheet_noise, {str(self.line.id): self.line.timesheet_noise})
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.write_date, write_date, "the invoice itself is not written")
        self.assertEqual((invoice.amount_untaxed, invoice.amount_total, invoice_line.quantity, invoice_line.price_subtotal), amounts)

    def test_invoice_printed_first(self):
        invoice = self.order._create_invoices()
        self.assertFalse(invoice.invoice_line_ids.timesheet_noise)
        invoice.action_post()
        noise = invoice._get_report_timesheets()['noise']
        self.assertEqual(invoice.invoice_line_ids.timesheet_noise, {str(self.line.id): self.line.timesheet_noise})
        self.assertEqual(self.order._get_report_timesheets()['noise'], noise)

    def test_disabled(self):
        self.env.company.timesheet_noise_minutes = 0
        self.assertFalse(self.order._get_report_timesheets()['noise'])
        self.assertFalse(self.line.timesheet_noise)

    def test_report(self):
        Report = self.env['ir.actions.report']
        html = Report._render_qweb_html(
            'odossey_timesheet_to_invoice.action_report_saleorder_hours', self.order.ids)[0].decode()
        noise = self.line.timesheet_noise
        self.assertTrue(noise)
        printed = re.findall(r'\d\d:\d\d', html[html.index('hours_invoiced_title'):])
        expected = ['%02d:%02d' % divmod(round(amount * 60 + delta), 60) for group in ('1-0', '0-0') for amount, delta in noise[group].values()]
        self.assertEqual([p for p in printed if p not in ('02:30', '00:45')], [e for e in expected if e not in ('02:30', '00:45')])
        self.assertIn('02:30', printed)
        self.assertIn('00:45', printed)
        # the standard timesheet report of the order prints the recorded hours
        html = Report._render_qweb_html('sale_timesheet.timesheet_report_sale_order', self.order.ids)[0].decode()
        self.assertIn('00:15', html)
