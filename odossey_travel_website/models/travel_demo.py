from datetime import timedelta

from odoo import fields, models


class TravelTrip(models.Model):
    _inherit = 'travel.trip'

    def _travel_demo_load_extra(self, demo):
        """Website demo: published trips (deposit, full payment only, payment in the trip
        currency, sold out) and online bookings in every situation."""
        res = super()._travel_demo_load_extra(demo)
        trips = demo['trips']
        today = fields.Date.context_today(self)
        (trips['puerto_plata'] | trips['europe'] | trips['iguazu'] | trips['bariloche']
         | trips['floripa']).write({'is_published': True})
        trips['europe'].web_currency = 'trip'          # paid in USD (card / wire transfer)
        trips['bariloche'].web_allow_deposit = False   # full payment online
        trips['puerto_plata'].website_description = (
            "<h3>Puerto Plata, all inclusive frente al mar</h3>"
            "<p>Vuelos desde Córdoba con Copa Airlines vía Panamá, 7 noches en el Emotions by "
            "Hodelpa (Playa Dorada) con todo incluido, traslados y dos excursiones: catamarán "
            "a Isla Paraíso y teleférico al Pico Isabel de Torres.</p>"
            "<p>Reservá con la seña y congelá el precio en dólares: el saldo se abona hasta 45 "
            "días antes de la salida.</p>")

        P = self._travel_demo_partner
        bd = self._travel_demo_birthdate
        ar = self.env.ref('base.ar')
        camila = P("Camila Benítez", '42333444', bd(1998, 3, 15), "Córdoba", 'x',
                   gender='female', phone='+54 351 555 0210')
        lucas_b = P("Lucas Benítez", '43444555', bd(2000, 8, 8), "Córdoba", 'x', gender='male')
        lucas = P("Lucas Moreno", '40111222', bd(1997, 1, 5), "Villa María", 'x',
                  gender='male', phone='+54 353 555 0133')
        martina = P("Martina Quiroga", '35111999', bd(1990, 4, 12), "Córdoba", 'x',
                    gender='female', phone='+54 351 555 0199', passport_number='AAU123000',
                    passport_country_id=ar.id,
                    passport_expiry_date=today + timedelta(days=900))
        lucas_q = P("Lucas Quiroga", '36222888', bd(1989, 9, 1), "Córdoba", 'x', gender='male',
                    passport_number='AAV456000', passport_country_id=ar.id,
                    passport_expiry_date=today + timedelta(days=900))
        valentina = P("Valentina Rodríguez", '41222333', bd(1999, 12, 3), "San Francisco", 'x',
                      gender='female')
        sergio = P("Sergio Ledesma", '26333111', bd(1977, 5, 23), "Córdoba", 'x',
                   gender='male')

        # Quotation just created online, waiting for the payment (it holds the seats)
        trips['iguazu']._web_create_booking(camila, camila | lucas_b)
        # Deposit paid online: invoiced and price frozen
        iguazu_web = trips['iguazu']._web_create_booking(lucas, lucas, room_type='single')
        iguazu_web.action_confirm()
        self._travel_demo_invoice_deposit(iguazu_web, memo="Pago online Mercado Pago")
        # USD trip sold online in pesos (converted at the rate of the day), deposit paid
        caribe_web = trips['puerto_plata']._web_create_booking(martina, martina | lucas_q)
        caribe_web.action_confirm()
        self._travel_demo_invoice_deposit(caribe_web, memo="Pago online Mercado Pago")
        # Full payment online (no deposit on this trip), then the customer used the
        # withdrawal button (botón de arrepentimiento) within the 10 days
        bariloche_web = trips['bariloche']._web_create_booking(valentina, valentina)
        bariloche_web.action_confirm()
        self._travel_demo_invoice_final(bariloche_web)
        bariloche_web.travel_withdrawal_date = fields.Datetime.now()
        bariloche_web.message_post(body=self.env._(
            "Withdrawal requested by the customer from the website (botón de "
            "arrepentimiento). Reason: %s", "Me cambiaron las vacaciones en el trabajo"))
        bariloche_web.activity_schedule(
            'mail.mail_activity_data_todo',
            summary=self.env._("Withdrawal request (arrepentimiento)"),
            note="Me cambiaron las vacaciones en el trabajo",
            user_id=(bariloche_web.trip_id.user_id or self.env.user).id)
        # Online quotation never paid: expired, the seats are free again
        expired = trips['europe']._web_create_booking(sergio, sergio, room_type='single')
        expired.validity_date = today - timedelta(days=3)
        return res
