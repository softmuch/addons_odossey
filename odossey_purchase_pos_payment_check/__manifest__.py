# License OPL-1
{
    "name": "Purchase Order POS Payment - Check",
    "summary": "Add cheque fields to the purchase-order payment popups, mirror image of l10n_latam_check_ext's pos.make.payment support.",
    "version": "19.0.1.0.0",
    "category": "Purchases",
    "license": "OPL-1",
    "author": "Odossey",
    "depends": ["odossey_purchase_pos_payment", "l10n_latam_check_ext"],
    "data": [
        "views/purchase_check_views.xml",
        "wizard/purchase_order_payment_views.xml",
        "wizard/purchase_order_pay_freely_views.xml",
    ],
    "installable": True,
}
