# License OPL-1
{
    "name": "Purchase Order POS Payment",
    "summary": "Pay purchase orders by registering negative pos.payment records, mirror image of a POS sale payment.",
    "version": "19.0.1.0.0",
    "category": "Purchases",
    "license": "OPL-1",
    "author": "Odossey",
    "depends": ["purchase", "point_of_sale", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_order_views.xml",
        "views/purchase_order_tree_views.xml",
        "views/pos_payment_views.xml",
        "wizard/purchase_order_payment_views.xml",
        "wizard/purchase_order_pay_freely_views.xml",
    ],
    "installable": True,
}
