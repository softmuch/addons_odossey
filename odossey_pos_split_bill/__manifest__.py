{
    "name": "Odossey || Point of sale split bill",
    "version": "18.0.1.0.4",
    "category": "Sales/Point of Sale",
    'author': 'Odossey',
    'website': "odossey.com",
    "sequence": 40,
    "description": """Odossey || Point of sale split bill""",
    "summary": """Odossey || Point of sale split bill""",
    "depends": ["pos_restaurant"],
    "data": [
        "views/pos_order_split_view.xml",
    ],
    "installable": True,
    "application": True,
    "assets": {
        "point_of_sale._assets_pos": [  
            "odossey_pos_split_bill/static/src/js/PosOrder.js",
            # reciept screen
            "odossey_pos_split_bill/static/src/js/RecieptSrceen.js",
            # "odossey_pos_split_bill/static/src/xml/ReceiptScreen.xml",
            # Ticket screen
            "odossey_pos_split_bill/static/src/js/TicketScreen.js",
            "odossey_pos_split_bill/static/src/xml/TicketScreen.xml",
            # Split info popup
            "odossey_pos_split_bill/static/src/js/splitInfoDisplayPopup.js",
            "odossey_pos_split_bill/static/src/xml/splitInfoDisplayPopup.xml",
            "odossey_pos_split_bill/static/src/scss/split_style.scss",
            # Tip screeen
            "odossey_pos_split_bill/static/src/js/TipScreenSplitPatch.js",
            "odossey_pos_split_bill/static/src/xml/TipScreenSplitPatch.xml",
            # Control buttons
            "odossey_pos_split_bill/static/src/js/ControlButtons.js",
            "odossey_pos_split_bill/static/src/xml/ControlButtons.xml",
            # Order line
            "odossey_pos_split_bill/static/src/js/OrderLine.js",
            "odossey_pos_split_bill/static/src/xml/OrderLine.xml",
            # Payment screen
            "odossey_pos_split_bill/static/src/js/PaymetScreenSplitPatch.js",
            "odossey_pos_split_bill/static/src/xml/PaymentScreenSplitPatch.xml",
            # Others
            "odossey_pos_split_bill/static/src/js/PaymentScreenPaymentLines.js",
            "odossey_pos_split_bill/static/src/js/posStore.js",
            "odossey_pos_split_bill/static/src/js/PosPayment.js",
            "odossey_pos_split_bill/static/src/js/ProductScreen.js",
            "odossey_pos_split_bill/static/src/js/PaymentScreenStatus.js",
            "odossey_pos_split_bill/static/src/js/OrderReciept.js",
            "odossey_pos_split_bill/static/src/xml/OrderReceipt.xml",
            # "odossey_pos_split_bill/static/src/xml/PaymentScreenDue.xml",
        ],
    },
    "license": "OPL-1",
}
