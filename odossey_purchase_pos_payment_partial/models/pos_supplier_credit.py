# License OPL-1
from odoo import fields, models


class PosSupplierCredit(models.Model):
    _name = 'pos.supplier.credit'
    _description = 'Supplier Credit Ledger (from Purchase Order overpayments)'
    _order = 'date desc, id desc'

    partner_id = fields.Many2one('res.partner', required=True, index=True, string='Supplier')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related='company_id.currency_id')
    # Positive: credit banked (a purchase order's overpayment left over after
    # covering the supplier's other partially-paid orders). Negative: credit
    # consumed (reconciled against a new order's own bill).
    amount = fields.Monetary(required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    origin_order_id = fields.Many2one(
        'purchase.order', string='From Order',
        help="Order whose overpayment generated this credit (set when amount > 0).",
    )
    used_order_id = fields.Many2one(
        'purchase.order', string='Applied To Order',
        help='Order this credit was used to pay (set when amount < 0).',
    )
    # The real `account.payment` whose residual this credit represents (set
    # on the positive/banking row). A negative/consuming row that draws on
    # the same banked amount points at the SAME account.payment, so how much
    # of it is still available can be found by summing every ledger row
    # sharing this reference (rather than needing to inspect the payment's
    # own move line residual directly).
    account_payment_id = fields.Many2one(
        'account.payment', string='Backing Payment', readonly=True,
        help='The real, already-posted outbound payment whose leftover, '
        'unreconciled residual this credit actually is. Using this credit '
        'later reconciles against THIS SAME payment -- it never creates a '
        'new bank/cash movement, since the money was already sent to the '
        'supplier when this payment was made.',
    )
