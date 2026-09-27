from odoo import fields, models, tools

LINE_KINDS = [
    ('revenue', "Revenue"),
    ('vat', "VAT"),
    ('perception', "Perception"),
    ('other_tax', "Other Taxes"),
    ('cost', "Supplier Cost"),
    ('fee', "Fees"),
]


class TravelProfitabilityReport(models.Model):
    """Net profitability of the trips from the posted accounting entries.

    * Customer invoices of the trip: revenue lines and tax lines split into VAT (tax groups
      with a VAT ARCA code), perceptions (tribute codes 06/07/08/09) and other taxes.
    * Vendor bills linked to the trip: supplier costs, or fees for products of the travel
      service type 'Payment / Bank Fees'.
    * Estimated gross income tax (IIBB) and payment fees from the rates of the settings.

    Net profit = net revenue - supplier costs - fees - IIBB. VAT and perceptions are collected
    on behalf of the tax authority and are not part of the agency income.
    Amounts in company currency.
    """
    _name = 'travel.profitability.report'
    _description = "Travel Net Profitability"
    _auto = False
    _order = 'date desc'

    move_id = fields.Many2one('account.move', string="Journal Entry", readonly=True)
    move_type = fields.Selection(related='move_id.move_type')
    trip_id = fields.Many2one('travel.trip', string="Trip", readonly=True)
    travel_group_id = fields.Many2one('travel.group', string="Group", readonly=True)
    partner_id = fields.Many2one('res.partner', string="Partner", readonly=True)
    product_id = fields.Many2one('product.product', string="Product", readonly=True)
    company_id = fields.Many2one('res.company', string="Company", readonly=True)
    currency_id = fields.Many2one('res.currency', string="Currency", readonly=True)
    date = fields.Date(string="Date", readonly=True)
    line_kind = fields.Selection(LINE_KINDS, string="Kind", readonly=True)
    gross_amount = fields.Monetary(string="Gross Invoiced", readonly=True)
    vat_amount = fields.Monetary(string="VAT", readonly=True)
    perception_amount = fields.Monetary(string="Perceptions", readonly=True)
    other_tax_amount = fields.Monetary(string="Other Taxes", readonly=True)
    revenue_amount = fields.Monetary(string="Net Revenue", readonly=True)
    cost_amount = fields.Monetary(string="Supplier Costs", readonly=True)
    fee_amount = fields.Monetary(string="Fees", readonly=True)
    iibb_amount = fields.Monetary(string="Gross Income Tax (IIBB)", readonly=True)
    net_amount = fields.Monetary(string="Net Profit", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    k.*,
                    k.revenue_amount - k.cost_amount - k.fee_amount - k.iibb_amount
                        AS net_amount
                FROM (
                    SELECT
                        l.id,
                        l.move_id,
                        l.trip_id,
                        l.travel_group_id,
                        l.partner_id,
                        l.product_id,
                        l.company_id,
                        l.currency_id,
                        l.date,
                        l.line_kind,
                        CASE WHEN l.line_kind IN ('revenue', 'vat', 'perception', 'other_tax')
                            THEN l.amount ELSE 0 END AS gross_amount,
                        CASE WHEN l.line_kind = 'vat' THEN l.amount ELSE 0 END AS vat_amount,
                        CASE WHEN l.line_kind = 'perception' THEN l.amount ELSE 0 END
                            AS perception_amount,
                        CASE WHEN l.line_kind = 'other_tax' THEN l.amount ELSE 0 END
                            AS other_tax_amount,
                        CASE WHEN l.line_kind = 'revenue' THEN l.amount ELSE 0 END
                            AS revenue_amount,
                        CASE WHEN l.line_kind = 'cost' THEN -l.amount ELSE 0 END AS cost_amount,
                        CASE
                            WHEN l.line_kind = 'fee' THEN -l.amount
                            WHEN l.line_kind IN ('revenue', 'vat', 'perception', 'other_tax')
                                THEN l.amount * COALESCE(l.fee_rate, 0) / 100.0
                            ELSE 0
                        END AS fee_amount,
                        CASE
                            WHEN l.line_kind = 'revenue'
                                THEN l.amount * COALESCE(l.iibb_rate, 0) / 100.0
                            WHEN l.line_kind = 'cost' AND l.iibb_base = 'margin'
                                THEN l.amount * COALESCE(l.iibb_rate, 0) / 100.0
                            ELSE 0
                        END AS iibb_amount
                    FROM (
                        SELECT
                            aml.id,
                            aml.move_id,
                            m.trip_id,
                            m.travel_group_id,
                            m.commercial_partner_id AS partner_id,
                            aml.product_id,
                            m.company_id,
                            c.currency_id,
                            m.date,
                            c.travel_iibb_rate AS iibb_rate,
                            c.travel_iibb_base AS iibb_base,
                            c.travel_payment_fee_rate AS fee_rate,
                            -aml.balance AS amount,
                            CASE
                                WHEN m.move_type IN ('out_invoice', 'out_refund')
                                     AND aml.display_type = 'product' THEN 'revenue'
                                WHEN m.move_type IN ('out_invoice', 'out_refund')
                                     AND tg.l10n_ar_vat_afip_code IS NOT NULL THEN 'vat'
                                WHEN m.move_type IN ('out_invoice', 'out_refund')
                                     AND tg.l10n_ar_tribute_afip_code IN ('06', '07', '08', '09')
                                     THEN 'perception'
                                WHEN m.move_type IN ('out_invoice', 'out_refund')
                                     THEN 'other_tax'
                                WHEN pt.travel_service_type = 'fee' THEN 'fee'
                                ELSE 'cost'
                            END AS line_kind
                        FROM account_move_line aml
                        JOIN account_move m ON m.id = aml.move_id
                        JOIN res_company c ON c.id = m.company_id
                        LEFT JOIN account_tax_group tg ON tg.id = aml.tax_group_id
                        LEFT JOIN product_product pp ON pp.id = aml.product_id
                        LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
                        WHERE m.state = 'posted'
                          AND m.trip_id IS NOT NULL
                          AND (
                              (m.move_type IN ('out_invoice', 'out_refund')
                               AND aml.display_type IN ('product', 'tax'))
                              OR (m.move_type IN ('in_invoice', 'in_refund')
                                  AND aml.display_type = 'product')
                          )
                    ) l
                ) k
            )
        """)
