{
    'name': 'Odossey || Travel',
    'version': '19.0.1.1.0',
    'category': 'Sales/Travel',
    'author': 'Odossey',
    'website': 'odossey.com',
    'summary': 'Travel agency management: trips, bookings, deposits, groups, '
               'passengers, forecast and net profitability (Argentina ready)',
    'description': """
Travel agency management (Community only)
=========================================
* Trips with services, capacity, itinerary and a calendar as main view.
* Bookings based on sale orders linked to a trip, grouped by trip.
* Deposit to freeze the price, balance tracking and cancellations with penalties.
* Family groups (one payer) and friends groups (one invoice per member).
* Revenue forecast weighted by configurable cancellation rates.
* Net profitability: VAT, perceptions, gross income tax (IIBB), fees and costs.
* Passenger data (passport, DNI) with automatic load from DNI PDF417 or passport MRZ.
* Birthday emails, CRM opportunities per trip.
""",
    'depends': [
        'sale_management',
        'sale_crm',
        'calendar',
        'contacts',
        'account',
        'l10n_ar',
    ],
    'data': [
        'security/travel_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/travel_cancellation_policy_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'report/travel_forecast_report_views.xml',
        'report/travel_profitability_report_views.xml',
        'report/travel_reports.xml',
        'report/travel_quotation_templates.xml',
        'report/travel_profitability_templates.xml',
        'wizard/travel_booking_cancel_views.xml',
        'wizard/travel_document_scan_views.xml',
        'views/travel_activity_views.xml',
        'views/travel_trip_views.xml',
        'views/travel_passenger_views.xml',
        'views/travel_group_views.xml',
        'views/travel_cancellation_policy_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'views/crm_lead_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/travel_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odossey_travel/static/src/scan/*',
        ],
        'web.assets_tests': [
            'odossey_travel/static/tests/tours/*',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'OPL-1',
}
