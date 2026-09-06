# License OPL-1
from odoo import fields, models


class L10nLatamCheck(models.Model):
    _inherit = "l10n_latam.check"

    # Core declares this `related='payment_id.currency_id'` with no
    # `store=True`/`readonly=False` -- same problem `l10n_latam_check_ext`
    # already fixed for `company_id`/`partner_id` (a check created there has
    # no `payment_id` yet, so any plain related off it resolves empty
    # forever). Needed here so a check handed over to a supplier still has
    # a real currency to compare against the outbound payment's.
    currency_id = fields.Many2one(related="payment_id.currency_id", store=True, readonly=False)

    handed_to_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Handed To",
        readonly=True,
        copy=False,
        help="Set when this third-party check was handed over to a "
        "supplier to settle a purchase order, instead of being deposited "
        "or going through core's own third-party-check-transfer flow "
        "(which requires the check to have first been received through a "
        "real journal -- not the case for a check tracked via "
        "l10n_latam_check_ext's instant, journal-less creation).",
    )
    handed_date = fields.Date(readonly=True, copy=False)
