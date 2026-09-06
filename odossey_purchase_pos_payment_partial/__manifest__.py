# License OPL-1
{
    "name": "Purchase Order POS Payment - Partial",
    "summary": "Track partial/paid status on purchase orders, redistribute supplier overpayments, and bank/reuse supplier credit -- mirror image of odossey_partial_payments_pos.",
    "version": "19.0.1.0.0",
    "category": "Purchases",
    "license": "OPL-1",
    "author": "Odossey",
    "depends": ["odossey_purchase_pos_payment"],
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_order_views.xml",
        "views/pos_supplier_credit_views.xml",
        "wizard/purchase_order_payment_views.xml",
        "wizard/purchase_order_pay_freely_views.xml",
    ],
    "installable": True,
}
