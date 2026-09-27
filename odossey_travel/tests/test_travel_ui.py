import unittest
from datetime import timedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import HttpCase, tagged

try:
    import websocket
except ImportError:
    websocket = None


@tagged('post_install', '-at_install')
class TestTravelUi(HttpCase):

    @unittest.skipIf(websocket is None, "websocket-client is required to run the tours")
    def test_travel_tour(self):
        today = fields.Date.today()
        company = self.env.ref('base.user_admin').company_id
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=company.ids))
        passenger = self.env['res.partner'].create({'name': "Tour Passenger"})
        trip = self.env['travel.trip'].create({
            'name': "Tour Trip Odossey",
            'destination': "Salta",
            'date_start': today + timedelta(days=60),
            'date_end': today + timedelta(days=65),
            'company_id': company.id,
        })
        trip.action_open()
        self.env['sale.order'].create({
            'partner_id': passenger.id,
            'company_id': company.id,
            'trip_id': trip.id,
            'travel_passenger_ids': [Command.create({'partner_id': passenger.id})],
        })
        self.start_tour('/odoo', 'odossey_travel_tour', login='admin')
