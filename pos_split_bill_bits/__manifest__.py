{
    "name": "Point of sale split bill | Point of sale split order | POS split bill | POS split invoices",
    "version": "18.0.1.0.4",
    "category": "Sales/Point of Sale",
    "author": "Terabits Technolab",
    "sequence": 40,
    "description": """ 
        Our odoo Point of Sale split bill module allows the user to split orders by persons. You can split the order and get reciespt of the splited amount.
        POS split bill | split by person | split order | split invoice | pos split invoice | devide amount in group | split by group 
        Point of sale split bill | split bill on point of sale | pos restaurant split table | pos split restaurant table 
        Odoo POS Split Bill | Point of Sale Split Order |Invoice Splitting in Odoo | Split Payment POS Module | POS Order Split by Persons
        Bill Splitting and Invoicing | Splitting Orders by Customers |POS Multi-Invoice Generation | Odoo POS Split Amounts | Separate Invoicing for Split Orders
        Odoo POS Multiple Payments | POS Bill Sharing|Split Bill by Items|POS Invoice Distribution|Dividing POS Orders|Share Expenses in POS|POS Check Splitting|Multiple Invoices from POS Orders
        POS Payment Allocation|Odoo POS Group Payment|Retail POS System | Retail Point Of Sale System | POS table orders merge | POS merge tables | Order list merge | POS order management | POS table management
    """,
    "summary": """ 
        Our odoo Point of Sale split bill module allows the user to split orders by persons. You can split the order and get reciespt of the splited amount.
        POS split bill | split by person | split order | split invoice | pos split invoice | devide amount in group | split by group 
        Point of sale split bill | split bill on point of sale | pos restaurant split table | pos split restaurant table 
        Odoo POS Split Bill | Point of Sale Split Order |Invoice Splitting in Odoo | Split Payment POS Module | POS Order Split by Persons|
        Bill Splitting and Invoicing | Splitting Orders by Customers | POS Multi-Invoice Generation | Odoo POS Split Amounts | Separate Invoicing for Split Orders
        
        Delight POS theme | Advanced POS theme | Theme POS | Odoo POS theme | Shopon POS | Multipurpose odoo pos theme | point of sale theme | ShopOn POS |
        POS restaurant theme | POS theme | all in one pos | pos layout |pos order| pos visibility control| product suggestion|Odoo POS customization |New customized pos theme for the modern generation |
        POS Brand New User Interface| Redesigned Look for POS | New Look and Features to existing POS Design| Gen X | Design |Custom POS theme |Retail POS system |POS customization | POS theme in Odoo | POS Dashboard | POS Mobile interface | POS tablet interface 

        Simplify Access Management | Manage - Hide Menu, Submenu, Fields, Action, Reports, Views, | Restrict/Read-Only User, Apps,  Fields, Export, Archive, Actions, Views, Reports, Delete items | Manage Access rights from one place | Hide Tabs and buttons | Multi Company supported. | Access Manager
    """,
    "depends": ["pos_restaurant"],
    "data": [],
    "installable": True,
    "application": True,
    "website": "https://www.terabits.xyz",
    "assets": {
        "point_of_sale._assets_pos": [  
            "pos_split_bill_bits/static/src/js/PosOrder.js",
            # reciept screen
            "pos_split_bill_bits/static/src/js/RecieptSrceen.js",
            # "pos_split_bill_bits/static/src/xml/ReceiptScreen.xml",
            # Ticket screen
            "pos_split_bill_bits/static/src/js/TicketScreen.js",
            "pos_split_bill_bits/static/src/xml/TicketScreen.xml",
            # Split info popup
            "pos_split_bill_bits/static/src/js/splitInfoDisplayPopup.js",
            "pos_split_bill_bits/static/src/xml/splitInfoDisplayPopup.xml",
            "pos_split_bill_bits/static/src/scss/split_style.scss",
            # Tip screeen
            "pos_split_bill_bits/static/src/js/TipScreenSplitPatch.js",
            "pos_split_bill_bits/static/src/xml/TipScreenSplitPatch.xml",
            # Control buttons
            "pos_split_bill_bits/static/src/js/ControlButtons.js",
            "pos_split_bill_bits/static/src/xml/ControlButtons.xml",
            # Order line
            "pos_split_bill_bits/static/src/js/OrderLine.js",
            "pos_split_bill_bits/static/src/xml/OrderLine.xml",
            # Payment screen
            "pos_split_bill_bits/static/src/js/PaymetScreenSplitPatch.js",
            "pos_split_bill_bits/static/src/xml/PaymentScreenSplitPatch.xml",
            # Others
            "pos_split_bill_bits/static/src/js/PaymentScreenPaymentLines.js",
            "pos_split_bill_bits/static/src/js/posStore.js",
            "pos_split_bill_bits/static/src/js/PosPayment.js",
            "pos_split_bill_bits/static/src/js/ProductScreen.js",
            "pos_split_bill_bits/static/src/js/PaymentScreenStatus.js",
            "pos_split_bill_bits/static/src/js/OrderReciept.js",
            "pos_split_bill_bits/static/src/xml/OrderReceipt.xml",
            # "pos_split_bill_bits/static/src/xml/PaymentScreenDue.xml",
        ],
    },
    "images": ["static/description/banner.png"],
    "license": "OPL-1",
    "price": 149.99,
    "currency": "USD",
    "live_test_url": "https://www.terabits.xyz/request_demo?source=index&version=18&app=pos_split_bill_bits",
}
