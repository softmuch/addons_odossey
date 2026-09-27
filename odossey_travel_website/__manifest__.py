{
    'name': 'Odossey || Travel Website',
    'version': '19.0.1.1.0',
    'category': 'Website/Website',
    'author': 'Odossey',
    'website': 'odossey.com',
    'summary': 'Book and pay trips online: deposit that freezes the price or full payment',
    'description': """
Online booking of trips (Community only)
========================================
* Public catalogue of the published trips (/viajes) with filters.
* Trip page with itinerary, what is included, seats left, price and deposit.
* Booking form (holder and passengers) creating the booking (sale order).
* Online payment with the standard payment providers (Mercado Pago, Stripe,
  wire transfer...): the customer pays the deposit (freezes the price) or the
  full amount; the balance can be paid later from the customer portal.
* Online payments are invoiced automatically and freeze the price.
* Seats are held while the online quotation is valid; overbooking protection.
* "My trips" in the customer portal and a withdrawal button (arrepentimiento).
""",
    'depends': ['website', 'odossey_travel'],
    'data': [
        'data/website_data.xml',
        'views/travel_trip_views.xml',
        'views/website_travel_templates.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_tests': [
            'odossey_travel_website/static/tests/tours/*',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'OPL-1',
}
