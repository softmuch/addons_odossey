from odoo import fields, models, tools


class RadioOccupancyReport(models.Model):
    """Occupancy of the commercial breaks per day: capacity and seconds planned/aired."""
    _name = 'radio.occupancy.report'
    _description = "Break Occupancy"
    _auto = False
    _order = 'date, time'

    date = fields.Date(readonly=True)
    break_id = fields.Many2one('radio.break', string="Break", readonly=True)
    program_id = fields.Many2one('radio.program', string="Program", readonly=True)
    daypart_id = fields.Many2one('radio.daypart', string="Daypart", readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    time = fields.Float(readonly=True)
    capacity = fields.Integer(string="Capacity (s)", readonly=True, aggregator='sum')
    used = fields.Integer(string="Sold (s)", readonly=True, aggregator='sum')
    free = fields.Integer(string="Free (s)", readonly=True, aggregator='sum')
    occupancy = fields.Float(string="Occupancy (%)", readonly=True, aggregator='avg')
    spot_count = fields.Integer(string="Spots", readonly=True, aggregator='sum')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH days AS (
                    SELECT d::date AS date
                      FROM generate_series(CURRENT_DATE - 60, CURRENT_DATE + 60,
                                           interval '1 day') d
                ),
                slots AS (
                    SELECT days.date, b.id AS break_id, b.program_id, p.daypart_id,
                           b.company_id, b.time, b.capacity
                      FROM days
                      JOIN radio_break b ON TRUE
                      JOIN radio_program p ON p.id = b.program_id AND p.active
                      JOIN radio_program_radio_weekday_rel r ON r.radio_program_id = p.id
                      JOIN radio_weekday w ON w.id = r.radio_weekday_id
                     WHERE w.code = (EXTRACT(ISODOW FROM days.date)::int - 1)
                ),
                used AS (
                    SELECT e.break_id, e.date,
                           SUM(CASE WHEN f.uses_break THEN e.duration ELSE 0 END) AS used,
                           COUNT(*) AS spot_count
                      FROM radio_emission e
                      JOIN radio_ad_format f ON f.id = e.format_id
                     WHERE e.state IN ('planned', 'aired') AND e.break_id IS NOT NULL
                  GROUP BY e.break_id, e.date
                )
                SELECT ROW_NUMBER() OVER (ORDER BY s.date, s.break_id) AS id,
                       s.date, s.break_id, s.program_id, s.daypart_id, s.company_id, s.time,
                       s.capacity,
                       COALESCE(u.used, 0) AS used,
                       GREATEST(s.capacity - COALESCE(u.used, 0), 0) AS free,
                       CASE WHEN s.capacity > 0
                            THEN LEAST(100.0 * COALESCE(u.used, 0) / s.capacity, 100.0)
                            ELSE 0 END AS occupancy,
                       COALESCE(u.spot_count, 0) AS spot_count
                  FROM slots s
             LEFT JOIN used u ON u.break_id = s.break_id AND u.date = s.date
            )
        """)


class RadioRevenueReport(models.Model):
    """Advertising revenue from the posted invoices of the radio contracts."""
    _name = 'radio.revenue.report'
    _description = "Radio Advertising Revenue"
    _auto = False
    _order = 'date desc'

    date = fields.Date(readonly=True)
    move_id = fields.Many2one('account.move', string="Invoice", readonly=True)
    subscription_id = fields.Many2one('sale.subscription', string="Contract", readonly=True)
    partner_id = fields.Many2one('res.partner', string="Invoiced Partner", readonly=True)
    advertiser_id = fields.Many2one('res.partner', string="Advertiser", readonly=True)
    agency_id = fields.Many2one('res.partner', string="Agency", readonly=True)
    user_id = fields.Many2one('res.users', string="Salesperson", readonly=True)
    program_id = fields.Many2one('radio.program', string="Program", readonly=True)
    format_id = fields.Many2one('radio.ad.format', string="Format", readonly=True)
    daypart_id = fields.Many2one('radio.daypart', string="Daypart", readonly=True)
    product_id = fields.Many2one('product.product', string="Product", readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    is_commission = fields.Boolean(string="Agency Commission", readonly=True)
    is_barter = fields.Boolean(string="Barter", readonly=True)
    is_official = fields.Boolean(string="Official", readonly=True)
    quantity = fields.Float(readonly=True)
    amount = fields.Monetary(string="Net Amount", readonly=True,
                             help="Untaxed amount in company currency (credit notes deducted).")
    enacom_fee = fields.Monetary(string="ENACOM Fee", readonly=True,
                                 help="Estimated fee of Law 26.522 on the net amount.")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT aml.id,
                       m.invoice_date AS date,
                       m.id AS move_id,
                       s.id AS subscription_id,
                       m.commercial_partner_id AS partner_id,
                       s.partner_id AS advertiser_id,
                       s.radio_agency_id AS agency_id,
                       COALESCE(m.invoice_user_id, s.user_id) AS user_id,
                       aml.radio_program_id AS program_id,
                       aml.radio_format_id AS format_id,
                       aml.radio_daypart_id AS daypart_id,
                       aml.product_id,
                       m.company_id,
                       c.currency_id,
                       (aml.product_id IS NOT NULL
                        AND aml.product_id = c.radio_agency_commission_product_id) AS is_commission,
                       COALESCE(s.radio_is_barter, FALSE) AS is_barter,
                       COALESCE(s.radio_is_official, FALSE) AS is_official,
                       aml.quantity * (CASE WHEN m.move_type = 'out_refund' THEN -1 ELSE 1 END)
                           AS quantity,
                       -aml.balance AS amount,
                       -aml.balance * COALESCE(c.radio_enacom_rate, 0) / 100.0 AS enacom_fee
                  FROM account_move_line aml
                  JOIN account_move m ON m.id = aml.move_id
                  JOIN sale_subscription s ON s.id = m.subscription_id
                  JOIN res_company c ON c.id = m.company_id
                 WHERE m.state = 'posted'
                   AND m.move_type IN ('out_invoice', 'out_refund')
                   AND aml.display_type = 'product'
                   AND s.radio_contract
            )
        """)


class ReportRadioCertificate(models.AbstractModel):
    _name = 'report.odossey_radio.report_radio_certificate'
    _description = "Broadcast Certificate"

    def _get_report_values(self, docids, data=None):
        from dateutil.relativedelta import relativedelta
        data = data or {}
        ctx = self.env.context
        date_from = data.get('radio_date_from') or ctx.get('radio_date_from')
        date_to = data.get('radio_date_to') or ctx.get('radio_date_to')
        today = fields.Date.context_today(self)
        if not date_from or not date_to:
            first = today.replace(day=1)
            date_from, date_to = first - relativedelta(months=1), first - relativedelta(days=1)
        date_from, date_to = fields.Date.to_date(date_from), fields.Date.to_date(date_to)
        # with `data` the web client prints without ids: fall back on the ones of the data
        docids = docids or data.get('ids') or ctx.get('active_ids') or []
        docs = self.env['sale.subscription'].browse(docids)
        lines = {doc.id: doc._radio_certificate_emissions(date_from, date_to) for doc in docs}
        return {
            'doc_ids': docids, 'doc_model': 'sale.subscription', 'docs': docs,
            'date_from': date_from, 'date_to': date_to, 'lines': lines, 'today': today,
        }


class ReportRadioLog(models.AbstractModel):
    _name = 'report.odossey_radio.report_radio_log'
    _description = "Daily Log"

    def _get_report_values(self, docids, data=None):
        emissions = self.env['radio.emission'].browse(docids).filtered(
            lambda e: e.state != 'cancelled'
        ).sorted(lambda e: (e.date, e.planned_time, e.program_id.id, e.sequence, e.id))
        days = []
        for day in sorted(set(emissions.mapped('date'))):
            day_emissions = emissions.filtered(lambda e, d=day: e.date == d)
            blocks = []
            for brk in day_emissions.break_id.sorted('time'):
                items = day_emissions.filtered(lambda e, b=brk: e.break_id == b)
                blocks.append({'break': brk, 'items': items, 'seconds': sum(items.mapped('duration'))})
            orphans = day_emissions.filtered(lambda e: not e.break_id)
            days.append({'date': day, 'blocks': blocks, 'orphans': orphans})
        return {'doc_ids': docids, 'doc_model': 'radio.emission', 'docs': emissions,
                'days': days}


class ReportRadioGrid(models.AbstractModel):
    _name = 'report.odossey_radio.report_radio_grid'
    _description = "Programming Grid"

    def _get_report_values(self, docids, data=None):
        Program = self.env['radio.program']
        return {'doc_ids': docids, 'doc_model': 'radio.program', 'docs': Program.browse(docids),
                'grid': Program._grid_data(), 'company': self.env.company}
