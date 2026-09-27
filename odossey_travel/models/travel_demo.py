import unicodedata
from datetime import datetime, time, timedelta

import pytz

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

DEMO_MARK = 'Puerto Plata - All Inclusive'


class TravelTrip(models.Model):
    _inherit = 'travel.trip'

    # ------------------------------------------------------------------
    # Demo data on demand (Settings > Travel > Load Demo Data)
    # ------------------------------------------------------------------
    def _travel_demo_tax(self, vat_code, tax_use='sale'):
        return self.env['account.tax'].search([
            ('company_id', 'in', self.env.company.parent_ids.ids),
            ('type_tax_use', '=', tax_use),
            ('tax_group_id.l10n_ar_vat_afip_code', '=', vat_code),
        ], limit=1)

    def _travel_demo_product(self, name, service_type, vat_code, price=0.0, cost=0.0,
                             sale_ok=True):
        taxes = self._travel_demo_tax(vat_code)
        purchase_taxes = self._travel_demo_tax(vat_code, 'purchase')
        return self.env['product.product'].create({
            'name': name,
            'type': 'service',
            'sale_ok': sale_ok,
            'purchase_ok': True,
            'invoice_policy': 'order',
            'travel_service_type': service_type,
            'list_price': price,
            'standard_price': cost,
            'taxes_id': [Command.set(taxes.ids)],
            'supplier_taxes_id': [Command.set(purchase_taxes.ids)],
            'company_id': self.env.company.id,
        })

    @staticmethod
    def _travel_demo_email(name):
        ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
        parts = ascii_name.lower().split()
        return f"{parts[0]}.{parts[-1]}@example.com"

    def _travel_demo_partner(self, name, dni, birthdate, **vals):
        values = {
            'name': name,
            'vat': dni,
            'birthdate': birthdate,
            'email': self._travel_demo_email(name),
            'country_id': self.env.ref('base.ar').id,
            'nationality_id': self.env.ref('base.ar').id,
            'l10n_latam_identification_type_id': self.env.ref('l10n_ar.it_dni').id,
            'l10n_ar_afip_responsibility_type_id': self.env.ref('l10n_ar.res_CF').id,
            'lang': 'es_AR' if self.env['res.lang']._lang_get('es_AR') else self.env.lang,
        }
        values.update(vals)
        partner = self.env['res.partner'].search(
            [('vat', '=', dni), ('is_company', '=', False)], limit=1)
        if partner:
            # reuse the existing contact, only completing the missing data
            partner.write({key: value for key, value in values.items()
                           if value and not partner[key] and key != 'lang'})
            return partner
        return self.env['res.partner'].create(values)

    def _travel_demo_company_partner(self, name, cuit):
        Partner = self.env['res.partner']
        return Partner.search([('vat', '=', cuit), ('is_company', '=', True)], limit=1) \
            or Partner.create({
                'name': name, 'is_company': True, 'vat': cuit,
                'l10n_latam_identification_type_id': self.env.ref('l10n_ar.it_cuit').id,
                'l10n_ar_afip_responsibility_type_id': self.env.ref('l10n_ar.res_IVARI').id,
            })

    def _travel_demo_activity(self, trip, name, activity_type, day, hour, hours, **vals):
        tz = pytz.timezone(self.env.user.tz or 'America/Argentina/Buenos_Aires')
        local = tz.localize(datetime.combine(trip.date_start + timedelta(days=day), time(hour, 0)))
        start = local.astimezone(pytz.utc).replace(tzinfo=None)
        values = {
            'trip_id': trip.id,
            'name': name,
            'activity_type': activity_type,
            'start': start,
            'stop': start + timedelta(hours=hours),
        }
        values.update(vals)
        return self.env['travel.activity'].create(values)

    def _travel_demo_pay(self, invoices, amount=None):
        for invoice in invoices:
            if invoice.state == 'draft':
                invoice.action_post()
            self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=invoice.ids,
            ).create({'amount': amount or invoice.amount_residual})._create_payments()

    def _travel_demo_invoice_deposit(self, orders, pay=True):
        for order in orders:
            wizard = self.env['sale.advance.payment.inv'].with_context(
                active_model='sale.order', active_ids=order.ids).create({
                    'advance_payment_method': 'fixed',
                    'fixed_amount': order.travel_deposit_required,
                })
            invoices = wizard._create_invoices(order)
            invoices.action_post()
            if pay:
                self._travel_demo_pay(invoices)

    def _travel_demo_invoice_final(self, orders, pay=True):
        invoices = orders._create_invoices(grouped=True, final=True)
        invoices.action_post()
        if pay:
            self._travel_demo_pay(invoices)
        return invoices

    def _travel_load_demo_data(self):
        company = self.env.company
        if self.search_count([('name', '=', DEMO_MARK), ('company_id', '=', company.id)]):
            raise UserError(self.env._("The demo data is already loaded for %s.", company.name))
        if not company.chart_template or not company.chart_template.startswith('ar'):
            raise UserError(self.env._(
                "The demo data needs a company with the Argentinian chart of accounts."))
        today = fields.Date.context_today(self)
        usd = self.env.ref('base.USD')
        if not usd.active:
            usd.active = True
        if company.currency_id != usd and not self.env['res.currency.rate'].search_count(
                [('currency_id', '=', usd.id), ('company_id', '=', company.id)]):
            self.env['res.currency.rate'].create({
                'currency_id': usd.id, 'company_id': company.id,
                'name': today - timedelta(days=365), 'inverse_company_rate': 1404.5,
            })
        company.write({'travel_iibb_rate': 4.75, 'travel_iibb_base': 'margin',
                       'travel_payment_fee_rate': 1.5, 'travel_file_number': '20413'})

        # Services with the VAT treatment of the example invoice (ARCA)
        flight = self._travel_demo_product("International flight ticket", 'flight', '2')
        ground_abroad = self._travel_demo_product("Ground services abroad", 'ground', '1')
        ground_local = self._travel_demo_product("Ground services in Argentina", 'ground', '5')
        bus = self._travel_demo_product("National bus transport", 'transfer', '4')
        agency = self._travel_demo_product("Agency services (commission)", 'commission', '5')
        assistance = self._travel_demo_product("Travel assistance", 'assistance', '5')
        fee = self._travel_demo_product("Card processing fees", 'fee', '5', sale_ok=False)

        policy = self.env.ref('odossey_travel.cancellation_policy_standard',
                              raise_if_not_found=False) or self.env['travel.cancellation.policy']
        operator = self._travel_demo_company_partner("Caribe Operator S.A.", '30714295698')
        bank = self._travel_demo_company_partner("Card Payments Gateway", '30712345674')
        ar = self.env.ref('base.ar')
        do = self.env.ref('base.do')

        # Trips
        puerto_plata = self.create({
            'name': DEMO_MARK, 'destination': "Puerto Plata, Dominican Republic",
            'country_id': do.id, 'currency_id': usd.id,
            'date_start': today + timedelta(days=170), 'date_end': today + timedelta(days=177),
            'capacity': 20, 'min_pax': 10, 'deposit_type': 'fixed', 'deposit_amount': 930,
            'balance_due_days': 45, 'fixed_cost': 800, 'cancellation_policy_id': policy.id,
            'includes_flight': True, 'includes_lodging': True, 'includes_transfer': True,
            'not_included': "Travel assistance, tips", 'color': 4,
            'component_ids': [
                Command.create({'product_id': flight.id, 'name': "TICKET AEREOS",
                                'price_unit': 1150, 'cost_unit': 1090, 'supplier_id': operator.id}),
                Command.create({'product_id': ground_abroad.id, 'name': "SERVICIOS TERRESTRES",
                                'price_unit': 610, 'cost_unit': 520, 'supplier_id': operator.id}),
                Command.create({'product_id': agency.id, 'name': "SERVICIOS DE COMERCIALIZACION",
                                'price_unit': 60, 'cost_unit': 0}),
            ],
        })
        iguazu = self.create({
            'name': "Iguazu Falls - Long weekend", 'destination': "Puerto Iguazú, Misiones",
            'country_id': ar.id, 'date_start': today + timedelta(days=45),
            'date_end': today + timedelta(days=49), 'capacity': 30, 'min_pax': 15,
            'deposit_type': 'percent', 'deposit_percent': 30, 'balance_due_days': 20,
            'cancellation_policy_id': policy.id, 'includes_transfer': True,
            'includes_lodging': True, 'includes_excursions': True, 'color': 10,
            'component_ids': [
                Command.create({'product_id': bus.id, 'price_unit': 180000, 'cost_unit': 150000}),
                Command.create({'product_id': ground_local.id, 'price_unit': 420000,
                                'cost_unit': 350000}),
                Command.create({'product_id': agency.id, 'price_unit': 50000, 'cost_unit': 0}),
            ],
        })
        bariloche = self.create({
            'name': "Bariloche - Winter", 'destination': "San Carlos de Bariloche, Río Negro",
            'country_id': ar.id, 'date_start': today + timedelta(days=285),
            'date_end': today + timedelta(days=292), 'capacity': 40, 'min_pax': 25,
            'deposit_type': 'percent', 'deposit_percent': 25, 'balance_due_days': 30,
            'cancellation_policy_id': policy.id, 'includes_transfer': True,
            'includes_lodging': True, 'includes_assistance': True, 'color': 2,
            'component_ids': [
                Command.create({'product_id': bus.id, 'price_unit': 250000, 'cost_unit': 205000}),
                Command.create({'product_id': ground_local.id, 'price_unit': 780000,
                                'cost_unit': 640000}),
                Command.create({'product_id': assistance.id, 'price_unit': 45000,
                                'cost_unit': 30000}),
                Command.create({'product_id': agency.id, 'price_unit': 70000, 'cost_unit': 0}),
            ],
        })
        mendoza = self.create({
            'name': "Mendoza - Harvest festival", 'destination': "Mendoza",
            'country_id': ar.id, 'date_start': today - timedelta(days=200),
            'date_end': today - timedelta(days=196), 'capacity': 25, 'min_pax': 10,
            'deposit_type': 'percent', 'deposit_percent': 30, 'color': 7,
            'cancellation_policy_id': policy.id,
            'component_ids': [
                Command.create({'product_id': ground_local.id, 'price_unit': 380000,
                                'cost_unit': 300000}),
                Command.create({'product_id': agency.id, 'price_unit': 40000, 'cost_unit': 0}),
            ],
        })
        (puerto_plata | iguazu | bariloche | mendoza).action_open()

        # Itinerary of Puerto Plata (as in the example quotation)
        self._travel_demo_activity(
            puerto_plata, "Flight Córdoba - Panamá - Puerto Plata", 'flight', 0, 1, 10,
            carrier="Copa Airlines", flight_number="CM 270", route="COR - PTY - POP",
            stops="1 stop (1h37)", baggage="Personal item + carry on")
        self._travel_demo_activity(
            puerto_plata, "Emotions by Hodelpa", 'lodging', 0, 14, 7 * 24 - 4,
            hotel_stars='4', board_basis='all_inclusive', location="Playa Dorada")
        self._travel_demo_activity(puerto_plata, "Transfer airport - hotel", 'transfer', 0, 12, 1)
        self._travel_demo_activity(
            puerto_plata, "Paradise Island catamaran", 'excursion', 2, 9, 7,
            note="<p>Boat trip to a sandbank with snorkeling and lunch.</p>")
        self._travel_demo_activity(
            puerto_plata, "Cable car to Mount Isabel de Torres", 'excursion', 4, 10, 4,
            note="<p>The only cable car of the Caribbean, with a view of the whole city.</p>")
        self._travel_demo_activity(
            puerto_plata, "Flight Puerto Plata - Panamá - Córdoba", 'flight', 7, 12, 12,
            carrier="Copa Airlines", flight_number="CM 271", route="POP - PTY - COR",
            stops="1 stop (1h56)", baggage="Personal item + carry on")
        self._travel_demo_activity(puerto_plata, "Transfer hotel - airport", 'transfer', 7, 9, 1)

        # Travellers
        in_months = lambda months: today + timedelta(days=30 * months)  # noqa: E731
        juan = self._travel_demo_partner(
            "Juan Pérez", '25123456', today.replace(year=today.year - 48),
            gender='male', passport_number='AAB123456', passport_country_id=ar.id,
            passport_expiry_date=in_months(60), phone='+54 351 555 0101')
        maria = self._travel_demo_partner(
            "María González", '26987654', today.replace(year=1979, month=5, day=14),
            gender='female', passport_number='AAC654321', passport_country_id=ar.id,
            passport_expiry_date=in_months(7))
        sofia = self._travel_demo_partner(
            "Sofía Pérez", '48123123', today.replace(year=2012, month=8, day=2),
            gender='female', passport_number='AAD111222', passport_country_id=ar.id,
            passport_expiry_date=in_months(40))
        tomas = self._travel_demo_partner(
            "Tomás Pérez", '52321321', today.replace(year=2016, month=1, day=20),
            gender='male')
        friends = [
            self._travel_demo_partner(
                "Lucía Fernández", '38111222', today.replace(year=1994, month=3, day=3),
                gender='female', passport_number='AAE333444', passport_country_id=ar.id,
                passport_expiry_date=in_months(30)),
            self._travel_demo_partner(
                "Martín Gómez", '37222333', today.replace(year=1993, month=11, day=11),
                gender='male', passport_number='AAF555666', passport_country_id=ar.id,
                passport_expiry_date=in_months(48)),
            self._travel_demo_partner(
                "Carla Díaz", '39333444', today.replace(year=1995, month=7, day=21),
                gender='female', passport_number='AAG777888', passport_country_id=ar.id,
                passport_expiry_date=in_months(50)),
            self._travel_demo_partner(
                "Diego Romero", '36444555', today.replace(year=1992, month=9, day=9),
                gender='male', passport_number='AAH999000', passport_country_id=ar.id,
                passport_expiry_date=in_months(36)),
        ]
        others = [
            self._travel_demo_partner("Carlos Medina", '20555666',
                                      today.replace(year=1970, month=2, day=12), gender='male'),
            self._travel_demo_partner("Ana Torres", '30666777',
                                      today.replace(year=1985, month=6, day=30), gender='female'),
            self._travel_demo_partner("Pablo Ruiz", '31777888',
                                      today.replace(year=1987, month=4, day=4), gender='male'),
            self._travel_demo_partner("Laura Sosa", '32888999',
                                      today.replace(year=1989, month=12, day=24), gender='female'),
        ]

        # Family group: the father pays for everybody -> one booking, one invoice
        family = self.env['travel.group'].create({
            'name': "Pérez Family", 'trip_id': puerto_plata.id, 'group_type': 'family',
            'leader_id': juan.id, 'member_ids': [Command.set((juan | maria | sofia | tomas).ids)],
        })
        family.action_create_bookings()
        family_order = family.sale_order_ids
        family_order.travel_passenger_ids.filtered(
            lambda p: p.partner_id in (sofia | tomas)).write({'passenger_type': 'child'})
        family_order.action_confirm()
        self._travel_demo_invoice_deposit(family_order)

        # Friends group: every member pays his own part -> one booking / invoice each
        friends_group = self.env['travel.group'].create({
            'name': "University friends", 'trip_id': puerto_plata.id, 'group_type': 'friends',
            'leader_id': friends[0].id,
            'member_ids': [Command.set([f.id for f in friends])],
        })
        friends_group.action_create_bookings()
        friend_orders = friends_group.sale_order_ids.sorted('id')
        friend_orders[:3].action_confirm()
        self._travel_demo_invoice_deposit(friend_orders[:2])
        self._travel_demo_invoice_final(friend_orders[1:2])
        self._travel_demo_invoice_deposit(friend_orders[2:3], pay=False)

        # Iguazu: individual bookings, one cancelled
        SaleOrder = self.env['sale.order']
        iguazu_orders = SaleOrder
        for partner in others[:3]:
            iguazu_orders |= SaleOrder.create({
                'partner_id': partner.id, 'trip_id': iguazu.id,
                'travel_passenger_ids': [Command.create({'partner_id': partner.id})],
            })
        iguazu_orders._travel_load_services()
        iguazu_orders.action_confirm()
        self._travel_demo_invoice_deposit(iguazu_orders)
        cancel_wizard = self.env['travel.booking.cancel'].create({
            'sale_order_id': iguazu_orders[2].id, 'reason': "Health problem"})
        cancel_wizard.action_confirm()

        # Bariloche: open quotations
        for partner in others[3:] + [maria]:
            order = SaleOrder.create({
                'partner_id': partner.id, 'trip_id': bariloche.id,
                'travel_passenger_ids': [Command.create({'partner_id': partner.id})],
            })
            order._travel_load_services()

        # Mendoza: completed trip with invoices, costs and one cancellation (history)
        mendoza_orders = SaleOrder
        for partner in others:
            mendoza_orders |= SaleOrder.create({
                'partner_id': partner.id, 'trip_id': mendoza.id,
                'date_order': today - timedelta(days=260),
                'travel_passenger_ids': [Command.create({'partner_id': partner.id})],
            })
        mendoza_orders._travel_load_services()
        mendoza_orders.action_confirm()
        self._travel_demo_invoice_final(mendoza_orders[:3])
        self.env['travel.booking.cancel'].create({
            'sale_order_id': mendoza_orders[3].id, 'reason': "Changed plans",
            'cancel_date': today - timedelta(days=230)}).action_confirm()
        mendoza.action_confirm()
        mendoza.action_done()

        # Supplier costs linked to the trips
        purchase_journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'), ('company_id', '=', company.id)], limit=1)
        bill_type = self.env.ref('l10n_ar.dc_a_f', raise_if_not_found=False)
        bills = self.env['account.move']
        for number, (trip, partner, product, amount) in enumerate([
            (mendoza, operator, ground_local, 900000.0),
            (mendoza, bank, fee, 25000.0),
            (puerto_plata, operator, ground_abroad, 1500000.0),
        ], start=1):
            bill_vals = {
                'move_type': 'in_invoice',
                'partner_id': partner.id,
                'trip_id': trip.id,
                'invoice_date': min(today, trip.date_start),
                'journal_id': purchase_journal.id,
                'invoice_line_ids': [Command.create({
                    'product_id': product.id, 'quantity': 1, 'price_unit': amount})],
            }
            if purchase_journal.l10n_latam_use_documents and bill_type:
                bill_vals.update({'l10n_latam_document_type_id': bill_type.id,
                                  'l10n_latam_document_number': f'0001-{number:08d}'})
            bills |= self.env['account.move'].create(bill_vals)
        bills.action_post()

        # CRM opportunities
        lost_reason = self.env['crm.lost.reason'].search([], limit=1)
        Lead = self.env['crm.lead']
        leads = Lead.create([
            {'name': "Honeymoon in the Caribbean", 'type': 'opportunity', 'trip_id': puerto_plata.id,
             'partner_id': others[1].id, 'travel_pax_count': 2, 'expected_revenue': 5000000},
            {'name': "Family winter holidays", 'type': 'opportunity', 'trip_id': bariloche.id,
             'partner_id': others[2].id, 'travel_pax_count': 4, 'expected_revenue': 4580000},
            {'name': "Company retreat Iguazú", 'type': 'opportunity', 'trip_id': iguazu.id,
             'partner_id': others[0].id, 'travel_pax_count': 12, 'expected_revenue': 7800000},
            {'name': "Friends trip to Mendoza", 'type': 'opportunity', 'trip_id': mendoza.id,
             'partner_id': friends[2].id, 'travel_pax_count': 3, 'expected_revenue': 1260000},
        ])
        leads[2].action_set_won()
        leads[3].action_set_lost(lost_reason_id=lost_reason.id)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'travel.trip',
            'view_mode': 'kanban,list,form',
            'name': self.env._("Trips"),
        }
