import unicodedata
from datetime import date, datetime, time, timedelta

import pytz

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

# Old demo (before 19.0.1.1.0): trip name used to detect it
DEMO_MARK = 'Puerto Plata - All Inclusive'
# ir.model.data module of the demo records (they do not belong to any installed module)
DEMO_MODULE = 'odossey_travel_demo'


class TravelTrip(models.Model):
    _inherit = 'travel.trip'

    # ------------------------------------------------------------------
    # Demo data on demand (Settings > Travel > Load Demo Data)
    #
    # Coherent with a travel agency of Córdoba (Argentina), Responsable Inscripto:
    # every trip state, national / international trips in ARS / USD, fixed or percentage
    # deposits, every booking state, family / friends groups, company customers (invoice A),
    # consumers (invoice B), passenger types, rooms, document warnings, cancellations with
    # penalty or refund (credit note), partial payments, supplier bills, CRM pipeline and
    # birthdays. `_travel_demo_load_extra` lets other modules (website) add their own data.
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
        parts = ascii_name.lower().replace('.', '').split()
        return f"{parts[0]}.{parts[-1]}@example.com"

    @staticmethod
    def _travel_demo_cuit(prefix, number):
        """Valid CUIT/CUIL (check digit of ARCA) for the prefix (20, 23, 27, 30, 33...)."""
        digits = f"{prefix}{int(number):08d}"
        total = sum(int(d) * w for d, w in zip(digits, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
        check = 11 - total % 11
        return digits + str({11: 0, 10: 9}.get(check, check))

    @staticmethod
    def _travel_demo_birthdate(year, month, day):
        try:
            return date(year, month, day)
        except ValueError:  # 29 February
            return date(year, month, 28)

    def _travel_demo_partner(self, name, dni, birthdate, city=None, state=None, **vals):
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
        if city:
            values['city'] = city
        if state:
            values['state_id'] = self.env.ref(f'base.state_ar_{state}').id
        values.update(vals)
        partner = self.env['res.partner'].search(
            [('vat', '=', values['vat']), ('is_company', '=', False)], limit=1) \
            if values.get('vat') else self.env['res.partner']
        if partner:
            # reuse the existing contact, only completing the missing data
            partner.write({key: value for key, value in values.items()
                           if value and not partner[key] and key != 'lang'})
            return partner
        return self.env['res.partner'].create(values)

    def _travel_demo_company_partner(self, name, cuit, responsibility='res_IVARI', **vals):
        Partner = self.env['res.partner']
        partner = Partner.search([('vat', '=', cuit), ('is_company', '=', True)], limit=1)
        if partner:
            return partner
        values = {
            'name': name, 'is_company': True, 'vat': cuit,
            'country_id': self.env.ref('base.ar').id,
            'l10n_latam_identification_type_id': self.env.ref('l10n_ar.it_cuit').id,
            'l10n_ar_afip_responsibility_type_id': self.env.ref(f'l10n_ar.{responsibility}').id,
        }
        values.update(vals)
        return Partner.create(values)

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

    def _travel_demo_pay(self, invoices, amount=None, memo=None):
        for invoice in invoices:
            if invoice.state == 'draft':
                invoice.action_post()
            vals = {'amount': amount or invoice.amount_residual}
            if memo:
                vals['communication'] = memo
            self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=invoice.ids,
            ).create(vals)._create_payments()

    def _travel_demo_invoice_deposit(self, orders, pay=True, memo=None, extra_taxes=None):
        invoices = self.env['account.move']
        for order in orders:
            wizard = self.env['sale.advance.payment.inv'].with_context(
                active_model='sale.order', active_ids=order.ids).create({
                    'advance_payment_method': 'fixed',
                    'fixed_amount': order.travel_deposit_required,
                })
            invoice = wizard._create_invoices(order)
            if extra_taxes:
                for line in invoice.invoice_line_ids:
                    line.tax_ids |= extra_taxes
            invoice.action_post()
            if pay:
                self._travel_demo_pay(invoice, memo=memo)
            invoices |= invoice
        return invoices

    def _travel_demo_invoice_final(self, orders, pay=True, amount=None):
        invoices = orders._create_invoices(grouped=True, final=True)
        invoices.action_post()
        if pay:
            self._travel_demo_pay(invoices, amount=amount)
        return invoices

    def _travel_demo_booking(self, trip, payer, passengers, room='double', types=None,
                             rooming=None, **vals):
        """Quotation of `trip` paid by `payer` for `passengers` (list of partners)."""
        types = types or {}
        values = {
            'partner_id': payer.id,
            'trip_id': trip.id,
            'travel_passenger_ids': [
                Command.create({
                    'partner_id': p.id,
                    'sequence': i,
                    'room_type': room,
                    'passenger_type': types.get(p.id, 'adult'),
                    'room_number': rooming or False,
                }) for i, p in enumerate(passengers)
            ],
        }
        values.update(vals)
        order = self.env['sale.order'].create(values)
        order._travel_load_services()
        return order

    def _travel_demo_cancel(self, order, reason, penalty_percent=None, cancel_date=None):
        values = {'sale_order_id': order.id, 'reason': reason}
        if cancel_date:
            values['cancel_date'] = cancel_date
        if penalty_percent is not None:
            values.update({'penalty_percent': penalty_percent, 'penalty_amount': 0.0
                           if not penalty_percent else order.amount_total * penalty_percent / 100})
        self.env['travel.booking.cancel'].create(values).action_confirm()

    def _travel_demo_refund(self, invoice, reason):
        """Credit note for the whole invoice, posted and paid back to the customer."""
        wizard = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'reason': reason, 'journal_id': invoice.journal_id.id})
        wizard.refund_moves()
        credit_note = invoice.reversal_move_ids.filtered(lambda m: m.state == 'draft')
        credit_note.action_post()
        self._travel_demo_pay(credit_note)
        return credit_note

    def _travel_demo_bill(self, trip, partner, product, amount, number, bill_date=None):
        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'), ('company_id', '=', self.env.company.id)], limit=1)
        bill_type = self.env.ref('l10n_ar.dc_a_f', raise_if_not_found=False)
        today = fields.Date.context_today(self)
        values = {
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'trip_id': trip.id,
            'invoice_date': bill_date or min(today, trip.date_start),
            'journal_id': journal.id,
            'invoice_line_ids': [Command.create({
                'product_id': product.id, 'quantity': 1, 'price_unit': amount})],
        }
        if journal.l10n_latam_use_documents and bill_type:
            values.update({'l10n_latam_document_type_id': bill_type.id,
                           'l10n_latam_document_number': number})
        bill = self.env['account.move'].create(values)
        bill.action_post()
        return bill

    def _travel_demo_perception(self):
        """IIBB Córdoba perception (the agency is a perception agent): the chart of accounts
        brings it inactive at 0 %, the demo uses an active copy at 3 %."""
        Tax = self.env['account.tax'].with_context(active_test=False)
        name = "Percepción IIBB Córdoba 3%"
        tax = Tax.search([('company_id', '=', self.env.company.id), ('name', '=', name)], limit=1)
        if tax:
            return tax
        template = Tax.search([
            ('company_id', 'in', self.env.company.parent_ids.ids), ('type_tax_use', '=', 'sale'),
            ('tax_group_id.l10n_ar_tribute_afip_code', '=', '07'),
            ('tax_group_id.name', 'ilike', 'Córdoba'),
        ], limit=1)
        if not template:
            return Tax
        return template.copy({'name': name, 'amount': 3.0, 'active': True})

    def _travel_demo_register(self, records):
        """Keep a reference to the main demo records (ir.model.data) to recognise them."""
        company = self.env.company
        self.env['ir.model.data'].sudo().create([{
            'module': DEMO_MODULE,
            'name': f'{key}_{company.id}',
            'model': record._name,
            'res_id': record.id,
            'noupdate': True,
        } for key, record in records.items() if record and len(record) == 1])

    def _travel_demo_is_loaded(self):
        company = self.env.company
        return bool(
            self.env['ir.model.data'].sudo().search_count([
                ('module', '=', DEMO_MODULE), ('name', '=', f'trip_puerto_plata_{company.id}')])
            or self.search_count([('name', '=', DEMO_MARK), ('company_id', '=', company.id)]))

    def _travel_demo_load_extra(self, demo):
        """Hook for the modules extending the demo (e.g. website). `demo` is a dict with the
        main records created (trips, partners, bookings, products)."""
        return True

    def _travel_load_demo_data(self):
        company = self.env.company
        if self._travel_demo_is_loaded():
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
        # Agency of Córdoba: IIBB on the margin, card fees, file number (legajo EVyT)
        company.write({'travel_iibb_rate': 4.75, 'travel_iibb_base': 'margin',
                       'travel_payment_fee_rate': 1.5, 'travel_file_number': '20413'})
        english = company.with_context(lang='en_US')
        if english.travel_quotation_conditions == english._default_travel_quotation_conditions():
            for code, _name in self.env['res.lang'].get_installed():
                localized = company.with_context(lang=code)
                localized.travel_quotation_conditions = \
                    localized._default_travel_quotation_conditions()
        ar = self.env.ref('base.ar')
        demo = {}

        # ------------------------------------------------------------------
        # Services, with the VAT treatment of the example invoice (ARCA):
        # international flights exempt, services abroad not taxed, passenger transport
        # 10.5 %, services in Argentina and the agency commission 21 %.
        # ------------------------------------------------------------------
        flight_int = self._travel_demo_product("Pasaje aéreo internacional", 'flight', '2')
        flight_dom = self._travel_demo_product("Pasaje aéreo de cabotaje", 'flight', '4')
        ground_abroad = self._travel_demo_product("Servicios terrestres en el exterior", 'ground', '1')
        ground_local = self._travel_demo_product("Servicios terrestres en Argentina", 'ground', '5')
        lodging_local = self._travel_demo_product("Alojamiento en Argentina", 'lodging', '5')
        bus = self._travel_demo_product("Transporte en bus de larga distancia", 'transfer', '4')
        bus_int = self._travel_demo_product("Transporte internacional en bus", 'transfer', '2')
        excursion = self._travel_demo_product("Excursiones", 'excursion', '5')
        assistance = self._travel_demo_product("Asistencia al viajero", 'assistance', '5')
        agency = self._travel_demo_product("Servicios de comercialización", 'commission', '5')
        fee = self._travel_demo_product("Comisiones de cobro con tarjeta", 'fee', '5',
                                        sale_ok=False)
        demo['products'] = {
            'flight_int': flight_int, 'flight_dom': flight_dom, 'ground_abroad': ground_abroad,
            'ground_local': ground_local, 'lodging_local': lodging_local, 'bus': bus,
            'bus_int': bus_int, 'excursion': excursion, 'assistance': assistance,
            'agency': agency, 'fee': fee,
        }

        policy = self.env.ref('odossey_travel.cancellation_policy_standard',
                              raise_if_not_found=False) or self.env['travel.cancellation.policy']

        # Suppliers (Responsables Inscriptos: supplier invoices A)
        operator = self._travel_demo_company_partner(
            "Mayorista Caribe Tour S.A.", self._travel_demo_cuit(30, 71429569), city="CABA",
            state_id=self.env.ref('base.state_ar_c').id)
        europe_operator = self._travel_demo_company_partner(
            "Europa Circuitos S.A.", self._travel_demo_cuit(30, 71588224), city="CABA",
            state_id=self.env.ref('base.state_ar_c').id)
        bus_company = self._travel_demo_company_partner(
            "Transportes del Sol S.A.", self._travel_demo_cuit(30, 70877123), city="Córdoba",
            state_id=self.env.ref('base.state_ar_x').id)
        patagonia = self._travel_demo_company_partner(
            "Operador Patagonia Austral S.R.L.", self._travel_demo_cuit(30, 71233456),
            city="El Calafate")
        hotel_termas = self._travel_demo_company_partner(
            "Hotel Termas del Hondo S.R.L.", self._travel_demo_cuit(30, 70911222),
            city="Termas de Río Hondo")
        gateway = self._travel_demo_company_partner(
            "Pasarela de Pagos S.A.", self._travel_demo_cuit(30, 71234567), city="CABA")
        coordinator = self._travel_demo_partner(
            "Paula Ibarra", '29444555', self._travel_demo_birthdate(1982, 10, 5),
            city="Córdoba", state='x', gender='female', function="Coordinadora de grupos",
            phone='+54 351 555 0300')

        # ------------------------------------------------------------------
        # Trips: one per situation
        # ------------------------------------------------------------------
        Trip = self
        # 1. International, USD, fixed deposit, on sale (as in the example quotation)
        puerto_plata = Trip.create({
            'name': "Puerto Plata - All Inclusive",
            'destination': "Puerto Plata, República Dominicana",
            'country_id': self.env.ref('base.do').id, 'currency_id': usd.id,
            'date_start': today + timedelta(days=170), 'date_end': today + timedelta(days=177),
            'capacity': 20, 'min_pax': 10, 'deposit_type': 'fixed', 'deposit_amount': 930,
            'balance_due_days': 45, 'fixed_cost': 800, 'cancellation_policy_id': policy.id,
            'coordinator_id': coordinator.id,
            'includes_flight': True, 'includes_lodging': True, 'includes_transfer': True,
            'includes_excursions': True,
            'not_included': "Asistencia al viajero, propinas, gastos personales", 'color': 4,
            'description': "<p>7 noches en Playa Dorada con sistema all inclusive, vuelos desde "
                           "Córdoba con Copa Airlines vía Panamá y traslados.</p>",
            'component_ids': [
                Command.create({'product_id': flight_int.id, 'name': "TICKET AEREOS",
                                'price_unit': 1150, 'cost_unit': 1090, 'supplier_id': operator.id}),
                Command.create({'product_id': ground_abroad.id, 'name': "SERVICIOS TERRESTRES",
                                'price_unit': 610, 'cost_unit': 520, 'supplier_id': operator.id}),
                Command.create({'product_id': agency.id, 'name': "SERVICIOS DE COMERCIALIZACION",
                                'price_unit': 60, 'cost_unit': 0}),
            ],
        })
        # 2. International, USD, long circuit with passports to check
        europe = Trip.create({
            'name': "Europa clásica: Madrid, París y Roma",
            'destination': "Madrid, París y Roma", 'country_id': self.env.ref('base.es').id,
            'currency_id': usd.id,
            'date_start': today + timedelta(days=240), 'date_end': today + timedelta(days=253),
            'capacity': 25, 'min_pax': 15, 'deposit_type': 'fixed', 'deposit_amount': 1500,
            'balance_due_days': 60, 'cancellation_policy_id': policy.id,
            'coordinator_id': coordinator.id, 'includes_flight': True, 'includes_lodging': True,
            'includes_transfer': True, 'includes_excursions': True, 'includes_assistance': True,
            'not_included': "Almuerzos y cenas, tasas turísticas municipales", 'color': 9,
            'description': "<p>Salida grupal con coordinador desde Buenos Aires: 4 noches en "
                           "Madrid, 4 en París y 4 en Roma, hoteles 4★ con desayuno, "
                           "excursiones a Toledo y Versalles.</p>",
            'component_ids': [
                Command.create({'product_id': flight_int.id, 'name': "TICKET AEREOS",
                                'price_unit': 1450, 'cost_unit': 1380,
                                'supplier_id': europe_operator.id}),
                Command.create({'product_id': ground_abroad.id, 'name': "SERVICIOS TERRESTRES",
                                'price_unit': 3600, 'cost_unit': 3100,
                                'supplier_id': europe_operator.id}),
                Command.create({'product_id': assistance.id, 'name': "ASISTENCIA AL VIAJERO",
                                'price_unit': 180, 'cost_unit': 110}),
                Command.create({'product_id': agency.id, 'name': "SERVICIOS DE COMERCIALIZACION",
                                'price_unit': 150, 'cost_unit': 0}),
            ],
        })
        # 3. National, ARS, percentage deposit, departure soon (balance due in a few days)
        iguazu = Trip.create({
            'name': "Cataratas del Iguazú - Fin de semana largo",
            'destination': "Puerto Iguazú, Misiones", 'country_id': ar.id,
            'date_start': today + timedelta(days=45), 'date_end': today + timedelta(days=49),
            'capacity': 30, 'min_pax': 15, 'deposit_type': 'percent', 'deposit_percent': 30,
            'balance_due_days': 20, 'cancellation_policy_id': policy.id,
            'includes_transfer': True, 'includes_lodging': True, 'includes_excursions': True,
            'not_included': "Entrada al Parque Nacional (se abona en efectivo)", 'color': 10,
            'description': "<p>Bus semicama desde Córdoba, 3 noches en Puerto Iguazú con "
                           "desayuno, excursión a Cataratas lado argentino y Garganta del "
                           "Diablo.</p>",
            'component_ids': [
                Command.create({'product_id': bus.id, 'price_unit': 180000, 'cost_unit': 150000,
                                'supplier_id': bus_company.id}),
                Command.create({'product_id': ground_local.id, 'price_unit': 420000,
                                'cost_unit': 350000}),
                Command.create({'product_id': agency.id, 'price_unit': 50000, 'cost_unit': 0}),
            ],
        })
        # 4. National, ARS, winter holidays, on sale, company customers
        bariloche = Trip.create({
            'name': "Bariloche - Vacaciones de invierno",
            'destination': "San Carlos de Bariloche, Río Negro", 'country_id': ar.id,
            'date_start': today + timedelta(days=285), 'date_end': today + timedelta(days=292),
            'capacity': 40, 'min_pax': 25, 'deposit_type': 'percent', 'deposit_percent': 25,
            'balance_due_days': 30, 'cancellation_policy_id': policy.id,
            'includes_transfer': True, 'includes_lodging': True, 'includes_assistance': True,
            'includes_excursions': True, 'color': 2,
            'not_included': "Pases de ski y alquiler de equipos",
            'description': "<p>7 noches con media pensión, excursiones al Cerro Catedral, "
                           "Circuito Chico y Cerro Otto.</p>",
            'component_ids': [
                Command.create({'product_id': bus.id, 'price_unit': 250000, 'cost_unit': 205000,
                                'supplier_id': bus_company.id}),
                Command.create({'product_id': ground_local.id, 'price_unit': 780000,
                                'cost_unit': 640000}),
                Command.create({'product_id': assistance.id, 'price_unit': 45000,
                                'cost_unit': 30000}),
                Command.create({'product_id': agency.id, 'price_unit': 70000, 'cost_unit': 0}),
            ],
        })
        # 5. National, being planned (not on sale yet)
        salta = Trip.create({
            'name': "Salta y Jujuy - Quebrada de Humahuaca",
            'destination': "Salta, Purmamarca y Humahuaca", 'country_id': ar.id,
            'date_start': today + timedelta(days=150), 'date_end': today + timedelta(days=157),
            'capacity': 35, 'min_pax': 20, 'deposit_type': 'percent', 'deposit_percent': 30,
            'balance_due_days': 30, 'cancellation_policy_id': policy.id,
            'includes_transfer': True, 'includes_lodging': True, 'includes_excursions': True,
            'color': 3,
            'description': "<p>Bus desde Córdoba, 5 noches en Salta capital, Cafayate, "
                           "Purmamarca, Tilcara y Humahuaca. Peña folclórica con cena.</p>",
            'component_ids': [
                Command.create({'product_id': bus.id, 'price_unit': 290000, 'cost_unit': 240000,
                                'supplier_id': bus_company.id}),
                Command.create({'product_id': ground_local.id, 'price_unit': 690000,
                                'cost_unit': 560000}),
                Command.create({'product_id': excursion.id, 'name': "Tren a las Nubes",
                                'price_unit': 180000, 'cost_unit': 150000}),
                Command.create({'product_id': agency.id, 'price_unit': 60000, 'cost_unit': 0}),
            ],
        })
        # 6. International by bus, USD, percentage deposit, sold out and confirmed
        floripa = Trip.create({
            'name': "Florianópolis - Verano en bus",
            'destination': "Canasvieiras, Florianópolis (Brasil)",
            'country_id': self.env.ref('base.br').id, 'currency_id': usd.id,
            'date_start': today + timedelta(days=110), 'date_end': today + timedelta(days=119),
            'capacity': 8, 'min_pax': 6, 'deposit_type': 'percent', 'deposit_percent': 20,
            'balance_due_days': 30, 'cancellation_policy_id': policy.id,
            'includes_transfer': True, 'includes_lodging': True, 'includes_assistance': True,
            'color': 5,
            'description': "<p>Bus semicama con servicio a bordo, 7 noches en Canasvieiras con "
                           "desayuno, coordinador permanente.</p>",
            'component_ids': [
                Command.create({'product_id': bus_int.id, 'price_unit': 260, 'cost_unit': 210,
                                'supplier_id': bus_company.id}),
                Command.create({'product_id': ground_abroad.id, 'price_unit': 300,
                                'cost_unit': 250}),
                Command.create({'product_id': agency.id, 'price_unit': 20, 'cost_unit': 0}),
            ],
        })
        # 7. National by plane, cancelled by the agency (minimum not reached)
        calafate = Trip.create({
            'name': "El Calafate y Ushuaia",
            'destination': "El Calafate, Santa Cruz y Ushuaia, Tierra del Fuego",
            'country_id': ar.id,
            'date_start': today + timedelta(days=75), 'date_end': today + timedelta(days=82),
            'capacity': 20, 'min_pax': 12, 'deposit_type': 'percent', 'deposit_percent': 30,
            'balance_due_days': 30, 'cancellation_policy_id': policy.id,
            'includes_flight': True, 'includes_lodging': True, 'includes_excursions': True,
            'color': 1,
            'description': "<p>Glaciar Perito Moreno, navegación por el Canal Beagle y Tren del "
                           "Fin del Mundo.</p>",
            'component_ids': [
                Command.create({'product_id': flight_dom.id, 'price_unit': 520000,
                                'cost_unit': 480000}),
                Command.create({'product_id': ground_local.id, 'price_unit': 1100000,
                                'cost_unit': 900000, 'supplier_id': patagonia.id}),
                Command.create({'product_id': excursion.id, 'name': "Glaciar Perito Moreno",
                                'price_unit': 150000, 'cost_unit': 120000}),
                Command.create({'product_id': agency.id, 'price_unit': 90000, 'cost_unit': 0}),
            ],
        })
        # 8. National, travelling right now (confirmed)
        termas = Trip.create({
            'name': "Termas de Río Hondo - Escapada",
            'destination': "Termas de Río Hondo, Santiago del Estero", 'country_id': ar.id,
            'date_start': today - timedelta(days=2), 'date_end': today + timedelta(days=3),
            'capacity': 40, 'min_pax': 5, 'deposit_type': 'percent', 'deposit_percent': 30,
            'balance_due_days': 15, 'cancellation_policy_id': policy.id,
            'coordinator_id': coordinator.id,
            'includes_transfer': True, 'includes_lodging': True, 'color': 6,
            'description': "<p>5 noches con media pensión y piletas termales.</p>",
            'component_ids': [
                Command.create({'product_id': bus.id, 'price_unit': 160000, 'cost_unit': 130000,
                                'supplier_id': bus_company.id}),
                Command.create({'product_id': lodging_local.id, 'price_unit': 420000,
                                'cost_unit': 350000, 'supplier_id': hotel_termas.id}),
                Command.create({'product_id': agency.id, 'price_unit': 30000, 'cost_unit': 0}),
            ],
        })
        # 9. National, completed (history for the profitability report)
        mendoza = Trip.create({
            'name': "Mendoza - Fiesta de la Vendimia", 'destination': "Mendoza",
            'country_id': ar.id, 'date_start': today - timedelta(days=200),
            'date_end': today - timedelta(days=196), 'capacity': 25, 'min_pax': 4,
            'deposit_type': 'percent', 'deposit_percent': 30, 'color': 7,
            'cancellation_policy_id': policy.id, 'includes_lodging': True,
            'includes_excursions': True,
            'description': "<p>Bodegas de Luján de Cuyo y Valle de Uco, acto central de la "
                           "Vendimia.</p>",
            'component_ids': [
                Command.create({'product_id': ground_local.id, 'price_unit': 380000,
                                'cost_unit': 300000}),
                Command.create({'product_id': agency.id, 'price_unit': 40000, 'cost_unit': 0}),
            ],
        })
        (puerto_plata | europe | iguazu | bariloche | floripa | calafate | termas
         | mendoza).action_open()
        demo['trips'] = {
            'puerto_plata': puerto_plata, 'europe': europe, 'iguazu': iguazu,
            'bariloche': bariloche, 'salta': salta, 'floripa': floripa, 'calafate': calafate,
            'termas': termas, 'mendoza': mendoza,
        }

        # ------------------------------------------------------------------
        # Itineraries (calendar)
        # ------------------------------------------------------------------
        act = self._travel_demo_activity
        act(puerto_plata, "Vuelo Córdoba - Panamá - Puerto Plata", 'flight', 0, 1, 10,
            carrier="Copa Airlines", flight_number="CM 270", route="COR - PTY - POP",
            stops="1 escala (1h37)", baggage="Artículo personal + equipaje de mano")
        act(puerto_plata, "Emotions by Hodelpa", 'lodging', 0, 14, 7 * 24 - 4,
            hotel_stars='4', board_basis='all_inclusive', location="Playa Dorada")
        act(puerto_plata, "Traslado aeropuerto - hotel", 'transfer', 0, 12, 1)
        act(puerto_plata, "Catamarán a Isla Paraíso", 'excursion', 2, 9, 7,
            note="<p>Navegación a un banco de arena con snorkel y almuerzo.</p>")
        act(puerto_plata, "Teleférico al Pico Isabel de Torres", 'excursion', 4, 10, 4,
            note="<p>El único teleférico del Caribe, con vista a toda la ciudad.</p>")
        act(puerto_plata, "Traslado hotel - aeropuerto", 'transfer', 7, 9, 1)
        act(puerto_plata, "Vuelo Puerto Plata - Panamá - Córdoba", 'flight', 7, 12, 12,
            carrier="Copa Airlines", flight_number="CM 271", route="POP - PTY - COR",
            stops="1 escala (1h56)", baggage="Artículo personal + equipaje de mano")

        act(europe, "Vuelo Buenos Aires - Madrid", 'flight', 0, 13, 12, carrier="Iberia",
            flight_number="IB 6844", route="EZE - MAD", stops="Directo",
            baggage="1 valija de 23 kg + equipaje de mano")
        act(europe, "Hotel Madrid Centro", 'lodging', 1, 12, 4 * 24 - 4, hotel_stars='4',
            board_basis='breakfast', location="Gran Vía, Madrid")
        act(europe, "Excursión a Toledo", 'excursion', 3, 9, 8)
        act(europe, "Vuelo Madrid - París", 'flight', 5, 10, 2, carrier="Air Europa",
            flight_number="UX 1027", route="MAD - ORY", stops="Directo")
        act(europe, "Hotel París Montparnasse", 'lodging', 5, 15, 4 * 24 - 5, hotel_stars='4',
            board_basis='breakfast', location="Montparnasse, París")
        act(europe, "Palacio de Versalles", 'excursion', 7, 9, 6)
        act(europe, "Vuelo París - Roma", 'flight', 9, 11, 2, carrier="ITA Airways",
            flight_number="AZ 319", route="CDG - FCO", stops="Directo")
        act(europe, "Hotel Roma Termini", 'lodging', 9, 15, 4 * 24 - 5, hotel_stars='4',
            board_basis='breakfast', location="Termini, Roma")
        act(europe, "Museos Vaticanos y Capilla Sixtina", 'excursion', 11, 8, 5)
        act(europe, "Vuelo Roma - Madrid - Buenos Aires", 'flight', 13, 10, 16,
            carrier="Iberia", flight_number="IB 6845", route="FCO - MAD - EZE",
            stops="1 escala (2h10)", baggage="1 valija de 23 kg + equipaje de mano")

        act(iguazu, "Bus Córdoba - Puerto Iguazú", 'transfer', 0, 20, 20,
            supplier_id=bus_company.id, location="Terminal de Ómnibus de Córdoba")
        act(iguazu, "Hotel Amerian Portal del Iguazú", 'lodging', 1, 16, 3 * 24 - 6,
            hotel_stars='4', board_basis='breakfast', location="Puerto Iguazú")
        act(iguazu, "Cataratas lado argentino y Garganta del Diablo", 'excursion', 2, 8, 8)
        act(iguazu, "Bus Puerto Iguazú - Córdoba", 'transfer', 4, 10, 20,
            supplier_id=bus_company.id)

        act(bariloche, "Bus Córdoba - Bariloche", 'transfer', 0, 18, 22, supplier_id=bus_company.id)
        act(bariloche, "Hotel Cacique Inacayal", 'lodging', 1, 16, 7 * 24 - 8, hotel_stars='4',
            board_basis='half_board', location="Centro Cívico, Bariloche")
        act(bariloche, "Cerro Catedral", 'excursion', 2, 9, 8)
        act(bariloche, "Circuito Chico y Cerro Campanario", 'excursion', 4, 9, 5)

        act(salta, "Tren a las Nubes", 'excursion', 3, 7, 14, location="San Antonio de los Cobres")
        act(floripa, "Bus Córdoba - Florianópolis", 'transfer', 0, 16, 28,
            supplier_id=bus_company.id)
        act(floripa, "Pousada Canasvieiras", 'lodging', 1, 20, 7 * 24 - 10, hotel_stars='3',
            board_basis='breakfast', location="Canasvieiras")
        act(calafate, "Vuelo Córdoba - El Calafate", 'flight', 0, 8, 4,
            carrier="Aerolíneas Argentinas", flight_number="AR 1880", route="COR - FTE")
        act(calafate, "Glaciar Perito Moreno", 'excursion', 1, 8, 9, supplier_id=patagonia.id)
        act(termas, "Bus Córdoba - Termas de Río Hondo", 'transfer', 0, 7, 8,
            supplier_id=bus_company.id)
        act(termas, "Hotel Termas del Hondo", 'lodging', 0, 16, 5 * 24 - 6, hotel_stars='3',
            board_basis='half_board', supplier_id=hotel_termas.id)
        act(mendoza, "Bodegas de Luján de Cuyo", 'excursion', 1, 10, 6)

        # ------------------------------------------------------------------
        # Travellers (Argentinian consumers: invoice B)
        # ------------------------------------------------------------------
        P = self._travel_demo_partner
        bd = self._travel_demo_birthdate
        in_months = lambda months: today + timedelta(days=30 * months)  # noqa: E731
        do_pass = {'passport_country_id': ar.id}
        # Pérez family (Córdoba): the father pays for everybody
        juan = P("Juan Pérez", '25123456', bd(1978, 3, 10), "Córdoba", 'x', gender='male',
                 passport_number='AAB123456', passport_expiry_date=in_months(60),
                 phone='+54 351 555 0101', street="Bv. San Juan 450", **do_pass)
        maria = P("María González", '26987654', bd(1979, 5, 14), "Córdoba", 'x', gender='female',
                  passport_number='AAC654321', passport_expiry_date=in_months(7), **do_pass)
        sofia = P("Sofía Pérez", '48123123', bd(2012, 8, 2), "Córdoba", 'x', gender='female',
                  passport_number='AAD111222', passport_expiry_date=in_months(40), **do_pass)
        tomas = P("Tomás Pérez", '52321321', bd(2016, 1, 20), "Córdoba", 'x', gender='male')
        benjamin = P("Benjamín Pérez", '58456789', bd(today.year - 1, 2, 11), "Córdoba", 'x',
                     gender='male', passport_number='AAJ222333',
                     passport_expiry_date=in_months(58), **do_pass)
        # Friends from Rosario: each one pays his part
        lucia = P("Lucía Fernández", '38111222', bd(1994, 3, 3), "Rosario", 's', gender='female',
                  passport_number='AAE333444', passport_expiry_date=in_months(30), **do_pass)
        martin = P("Martín Gómez", '37222333', bd(1993, 11, 11), "Rosario", 's', gender='male',
                   passport_number='AAF555666', passport_expiry_date=in_months(48), **do_pass)
        carla = P("Carla Díaz", '39333444', bd(1995, 7, 21), "Rosario", 's', gender='female',
                  passport_number='AAG777888', passport_expiry_date=in_months(50), **do_pass)
        diego = P("Diego Romero", '36444555', bd(1992, 9, 9), "Rosario", 's', gender='male',
                  passport_number='AAH999000', passport_expiry_date=in_months(36), **do_pass)
        # Individual customers (birthday today and tomorrow: birthday emails)
        carlos = P("Carlos Medina", '20555666', bd(1970, 2, 12), "Villa Carlos Paz", 'x',
                   gender='male')
        ana = P("Ana Torres", '30666777', bd(1985, today.month, today.day), "Córdoba", 'x',
                gender='female', phone='+54 351 555 0177')
        tomorrow = today + timedelta(days=1)
        pablo = P("Pablo Ruiz", '31777888', bd(1987, tomorrow.month, tomorrow.day), "CABA", 'c',
                  gender='male')
        laura = P("Laura Sosa", '32888999', bd(1989, 12, 24), "Río Cuarto", 'x', gender='female')
        gabriela = P("Gabriela Herrera", '33111000', bd(1990, 6, 18), "Córdoba", 'x',
                     gender='female')
        federico = P("Federico Castro", '34222111', bd(1988, 4, 27), "Alta Gracia", 'x',
                     gender='male')
        # Europe: a couple, a monotributista (invoice A) without passport, a prospect
        roberto = P("Roberto Giménez", '22333444', bd(1968, 9, 30), "Córdoba", 'x',
                    gender='male', passport_number='AAK444555',
                    passport_expiry_date=in_months(70), **do_pass)
        silvia = P("Silvia Benítez", '23444555', bd(1970, 1, 15), "Córdoba", 'x',
                   gender='female', passport_number='AAL666777',
                   passport_expiry_date=in_months(10), **do_pass)
        mariano = P("Mariano Luna", '27888999', bd(1981, 5, 5), "Córdoba", 'x', gender='male',
                    vat=self._travel_demo_cuit(20, 27888999),
                    l10n_latam_identification_type_id=self.env.ref('l10n_ar.it_cuit').id,
                    l10n_ar_afip_responsibility_type_id=self.env.ref('l10n_ar.res_RM').id,
                    function="Arquitecto (monotributista)")
        julieta = P("Julieta Paz", '35999000', bd(1991, 10, 10), "Córdoba", 'x', gender='female')
        # Florianópolis: two families of four (children)
        sebastian = P("Sebastián Rodríguez", '28111333', bd(1980, 7, 7), "Córdoba", 'x',
                      gender='male', passport_number='AAM111000',
                      passport_expiry_date=in_months(45), **do_pass)
        paula = P("Paula Vera", '29222444', bd(1982, 2, 2), "Córdoba", 'x', gender='female',
                  passport_number='AAN222000', passport_expiry_date=in_months(45), **do_pass)
        mateo = P("Mateo Rodríguez", '50333555', bd(2014, 11, 30), "Córdoba", 'x',
                  gender='male', passport_number='AAO333000',
                  passport_expiry_date=in_months(45), **do_pass)
        emma = P("Emma Rodríguez", '54444666', bd(2018, 3, 25), "Córdoba", 'x',
                 gender='female', passport_number='AAP444000',
                 passport_expiry_date=in_months(45), **do_pass)
        gustavo = P("Gustavo Ortiz", '27555777', bd(1979, 8, 19), "Jesús María", 'x',
                    gender='male', passport_number='AAQ555000',
                    passport_expiry_date=in_months(30), **do_pass)
        cecilia = P("Cecilia Ríos", '28666888', bd(1981, 12, 1), "Jesús María", 'x',
                    gender='female', passport_number='AAR666000',
                    passport_expiry_date=in_months(30), **do_pass)
        lautaro = P("Lautaro Ortiz", '49777999', bd(2011, 5, 12), "Jesús María", 'x',
                    gender='male', passport_number='AAS777000',
                    passport_expiry_date=in_months(30), **do_pass)
        delfina = P("Delfina Ortiz", '53888000', bd(2017, 9, 3), "Jesús María", 'x',
                    gender='female', passport_number='AAT888000',
                    passport_expiry_date=in_months(30), **do_pass)
        # Termas: retired customers
        hector = P("Héctor Villalba", '10111222', bd(1952, 4, 14), "Córdoba", 'x', gender='male')
        norma = P("Norma Aguirre", '11222333', bd(1954, 8, 8), "Córdoba", 'x', gender='female')
        rosa = P("Rosa Maldonado", '12333444', bd(1950, 11, 20), "Cosquín", 'x', gender='female')
        olga = P("Olga Cabrera", '13444555', bd(1951, 3, 9), "Cosquín", 'x', gender='female')
        alberto = P("Alberto Quiroga", '14555666', bd(1953, 6, 1), "La Falda", 'x',
                    gender='male')
        # Calafate (trip cancelled by the agency)
        ignacio = P("Ignacio Ponce", '33555444', bd(1990, 1, 29), "Córdoba", 'x', gender='male')
        micaela = P("Micaela Ferreyra", '36666555', bd(1993, 4, 16), "Córdoba", 'x',
                    gender='female')
        # Company buying an incentive trip for its employees (Responsable Inscripto: invoice A)
        agro = self._travel_demo_company_partner(
            "Agro Pampa S.A.", self._travel_demo_cuit(30, 71098765), city="Marcos Juárez",
            state_id=self.env.ref('base.state_ar_x').id, email="rrhh@agropampa.example.com",
            phone='+54 3472 555 010')
        employees = [
            P("Nicolás Álvarez", '30123987', bd(1984, 7, 30), "Marcos Juárez", 'x', gender='male',
              parent_id=agro.id),
            P("Valeria Molina", '31234098', bd(1986, 2, 17), "Marcos Juárez", 'x',
              gender='female', parent_id=agro.id),
            P("Hernán Suárez", '29345109', bd(1983, 10, 22), "Marcos Juárez", 'x', gender='male',
              parent_id=agro.id),
            P("Florencia Acosta", '35456210', bd(1992, 12, 12), "Marcos Juárez", 'x',
              gender='female', parent_id=agro.id),
        ]
        demo['partners'] = {
            'juan': juan, 'maria': maria, 'sofia': sofia, 'tomas': tomas, 'benjamin': benjamin,
            'lucia': lucia, 'martin': martin, 'carla': carla, 'diego': diego, 'carlos': carlos,
            'ana': ana, 'pablo': pablo, 'laura': laura, 'gabriela': gabriela,
            'federico': federico, 'roberto': roberto, 'silvia': silvia, 'mariano': mariano,
            'julieta': julieta, 'agro': agro, 'coordinator': coordinator,
            'operator': operator, 'bus_company': bus_company,
        }

        Booking = self._travel_demo_booking
        # ------------------------------------------------------------------
        # Puerto Plata: family group (one payer, quadruple room, child and infant,
        # passports missing / expiring) and friends group (each one pays)
        # ------------------------------------------------------------------
        family = self.env['travel.group'].create({
            'name': "Familia Pérez", 'trip_id': puerto_plata.id, 'group_type': 'family',
            'leader_id': juan.id,
            'member_ids': [Command.set((juan | maria | sofia | tomas | benjamin).ids)],
            'note': "Piden cuna para Benjamín.",
        })
        family.action_create_bookings()
        family_order = family.sale_order_ids
        family_order.travel_passenger_ids.write({'room_type': 'quadruple', 'room_number': 'H1'})
        family_order.travel_passenger_ids.filtered(
            lambda p: p.partner_id in (sofia | tomas)).write({'passenger_type': 'child'})
        family_order.travel_passenger_ids.filtered(
            lambda p: p.partner_id == benjamin).write({'passenger_type': 'infant'})
        family_order.action_confirm()
        self._travel_demo_invoice_deposit(family_order)                   # price frozen

        friends_group = self.env['travel.group'].create({
            'name': "Amigos de la facultad", 'trip_id': puerto_plata.id,
            'group_type': 'friends', 'leader_id': lucia.id,
            'member_ids': [Command.set((lucia | martin | carla | diego).ids)],
        })
        friends_group.action_create_bookings()
        friend_orders = friends_group.sale_order_ids.sorted('id')
        friend_orders.travel_passenger_ids.write({'room_type': 'twin'})
        friend_orders[:2].travel_passenger_ids.write({'room_number': 'H2'})
        friend_orders[2:].travel_passenger_ids.write({'room_number': 'H3'})
        friend_orders[:3].action_confirm()
        self._travel_demo_invoice_deposit(friend_orders[:2])               # frozen
        self._travel_demo_invoice_final(friend_orders[1:2])                # fully paid
        self._travel_demo_invoice_deposit(friend_orders[2:3], pay=False)   # deposit pending
        # friend_orders[3]: still a quotation

        # ------------------------------------------------------------------
        # Europe: couple (deposit paid, passport expiring), monotributista (invoice A,
        # passport missing, deposit pending), prospect (quotation)
        # ------------------------------------------------------------------
        europe_couple = Booking(europe, roberto, roberto | silvia, room='double',
                                rooming='H1')
        europe_single = Booking(europe, mariano, mariano, room='single')
        Booking(europe, julieta, julieta, room='single')
        (europe_couple | europe_single).action_confirm()
        self._travel_demo_invoice_deposit(europe_couple)
        self._travel_demo_invoice_deposit(europe_single, pay=False)

        # ------------------------------------------------------------------
        # Iguazú: deposit paid, deposit pending, fully paid, cancelled with penalty
        # ------------------------------------------------------------------
        ig_carlos = Booking(iguazu, carlos, carlos, room='single')
        ig_ana = Booking(iguazu, ana, ana | laura, room='double')
        ig_pablo = Booking(iguazu, pablo, pablo, room='single')
        ig_gabriela = Booking(iguazu, gabriela, gabriela | federico, room='double')
        (ig_carlos | ig_ana | ig_pablo | ig_gabriela).action_confirm()
        self._travel_demo_invoice_deposit(ig_carlos | ig_pablo | ig_gabriela)
        self._travel_demo_invoice_deposit(ig_ana, pay=False)
        self._travel_demo_invoice_final(ig_gabriela)
        self._travel_demo_cancel(ig_pablo, "Problema de salud")

        # ------------------------------------------------------------------
        # Bariloche: company incentive trip (invoice A, deposit paid), fully paid family
        # (triple room), quotations
        # ------------------------------------------------------------------
        agro_order = Booking(bariloche, agro, employees, room='twin',
                             client_order_ref="OC 4512")
        agro_order.travel_passenger_ids[:2].write({'room_number': 'H1'})
        agro_order.travel_passenger_ids[2:].write({'room_number': 'H2'})
        agro_order.action_confirm()
        self._travel_demo_invoice_deposit(agro_order, extra_taxes=self._travel_demo_perception())
        bari_federico = Booking(bariloche, federico, federico | julieta | laura, room='triple')
        bari_federico.action_confirm()
        self._travel_demo_invoice_final(bari_federico)
        Booking(bariloche, gabriela, gabriela, room='single')
        # the DNI of the second passenger is still missing (document warning)
        joaquin = P("Joaquín Ledesma", None, bd(2008, 6, 20), "Córdoba", 'x', gender='male')
        Booking(bariloche, maria, maria | joaquin, room='double',
                types={joaquin.id: 'child'})

        # ------------------------------------------------------------------
        # Florianópolis: sold out, one family fully paid and one with the deposit
        # ------------------------------------------------------------------
        types = {mateo.id: 'child', emma.id: 'child', lautaro.id: 'child', delfina.id: 'child'}
        floripa_1 = Booking(floripa, sebastian, sebastian | paula | mateo | emma,
                            room='quadruple', types=types, rooming='H1')
        floripa_2 = Booking(floripa, gustavo, gustavo | cecilia | lautaro | delfina,
                            room='quadruple', types=types, rooming='H2')
        (floripa_1 | floripa_2).action_confirm()
        self._travel_demo_invoice_final(floripa_1)
        self._travel_demo_invoice_deposit(floripa_2)
        floripa.action_confirm()

        # ------------------------------------------------------------------
        # Termas (in progress): fully paid, one balance partially paid
        # ------------------------------------------------------------------
        termas_1 = Booking(termas, hector, hector | norma, room='double', rooming='H1')
        termas_2 = Booking(termas, rosa, rosa | olga, room='twin', rooming='H2')
        termas_3 = Booking(termas, alberto, alberto, room='single')
        (termas_1 | termas_2 | termas_3).action_confirm()
        self._travel_demo_invoice_final(termas_1 | termas_2)
        partial = self._travel_demo_invoice_final(termas_3, pay=False)
        self._travel_demo_pay(partial, amount=round(partial.amount_total * 0.6, 2))
        termas.action_confirm()

        # ------------------------------------------------------------------
        # Calafate: minimum not reached, the agency cancels the trip and refunds the
        # deposits (one credit note already issued, one refund still to do)
        # ------------------------------------------------------------------
        cal_1 = Booking(calafate, ignacio, ignacio, room='single')
        cal_2 = Booking(calafate, micaela, micaela, room='single')
        (cal_1 | cal_2).action_confirm()
        cal_invoices = self._travel_demo_invoice_deposit(cal_1 | cal_2)
        for order in cal_1 | cal_2:
            self._travel_demo_cancel(order, "Viaje cancelado por la agencia: no se alcanzó "
                                            "el mínimo de pasajeros", penalty_percent=0.0)
        self._travel_demo_refund(cal_invoices[:1], "Viaje cancelado por la agencia")
        cal_1.activity_ids.action_feedback(feedback="Nota de crédito emitida y transferencia "
                                                    "realizada.")
        calafate.action_cancel()

        # ------------------------------------------------------------------
        # Mendoza (completed): paid bookings, one cancelled 30 days after booking
        # ------------------------------------------------------------------
        mendoza_orders = self.env['sale.order']
        for partner in (carlos, ana, pablo, laura):
            mendoza_orders |= Booking(mendoza, partner, partner, room='double',
                                      date_order=today - timedelta(days=260))
        mendoza_orders.action_confirm()
        self._travel_demo_invoice_final(mendoza_orders[:3])
        self._travel_demo_cancel(mendoza_orders[3], "Cambio de planes",
                                 cancel_date=today - timedelta(days=230))
        mendoza.action_confirm()
        mendoza.action_done()
        demo['bookings'] = {
            'family': family_order, 'friends': friend_orders, 'europe_couple': europe_couple,
            'iguazu_ana': ig_ana, 'agro': agro_order, 'floripa_1': floripa_1,
        }

        # ------------------------------------------------------------------
        # Supplier bills linked to the trips (costs of the profitability report)
        # ------------------------------------------------------------------
        bill = self._travel_demo_bill
        bill(mendoza, operator, ground_local, 900000.0, '0003-00001542')
        bill(mendoza, gateway, fee, 25000.0, '0001-00020311')
        bill(puerto_plata, operator, ground_abroad, 1500000.0, '0003-00001601')
        bill(termas, bus_company, bus, 650000.0, '0005-00000871')
        bill(termas, hotel_termas, lodging_local, 1750000.0, '0002-00000412')
        bill(floripa, bus_company, bus_int, 1680000.0, '0005-00000880')
        bill(iguazu, bus_company, bus, 900000.0, '0005-00000902')

        # ------------------------------------------------------------------
        # CRM: the whole pipeline (new, qualified, proposition, won, lost)
        # ------------------------------------------------------------------
        stages = self.env['crm.stage'].search([], order='sequence')
        lost_reason = self.env['crm.lost.reason'].search([], limit=1)
        Lead = self.env['crm.lead']
        leads = Lead.create([
            {'name': "Contingente colegio San José - Salta", 'type': 'opportunity',
             'trip_id': salta.id, 'partner_name': "Colegio San José",
             'contact_name': "Mónica Luque", 'email_from': "monica.luque@example.com",
             'travel_pax_count': 30, 'expected_revenue': 36600000,
             'stage_id': stages[:1].id},
            {'name': "Jubilados Centro Vecinal - Salta", 'type': 'opportunity',
             'trip_id': salta.id, 'partner_id': hector.id, 'travel_pax_count': 12,
             'expected_revenue': 14640000, 'stage_id': stages[1:2].id or stages[:1].id},
            {'name': "Luna de miel en el Caribe", 'type': 'opportunity',
             'trip_id': puerto_plata.id, 'partner_id': julieta.id, 'travel_pax_count': 2,
             'expected_revenue': 5100000, 'stage_id': stages[2:3].id or stages[:1].id},
            {'name': "Vacaciones de invierno en familia", 'type': 'opportunity',
             'trip_id': bariloche.id, 'partner_id': sebastian.id, 'travel_pax_count': 4,
             'expected_revenue': 4580000, 'stage_id': stages[1:2].id or stages[:1].id},
            {'name': "Viaje de incentivo Agro Pampa", 'type': 'opportunity',
             'trip_id': bariloche.id, 'partner_id': agro.id, 'travel_pax_count': 4,
             'expected_revenue': 4580000},
            {'name': "Amigas a la Vendimia", 'type': 'opportunity', 'trip_id': mendoza.id,
             'partner_id': carla.id, 'travel_pax_count': 3, 'expected_revenue': 1260000},
            {'name': "Consulta web: Europa en pareja", 'type': 'lead',
             'contact_name': "Andrés Villar", 'email_from': "andres.villar@example.com",
             'phone': '+54 351 555 0420', 'trip_id': europe.id, 'travel_pax_count': 2},
        ])
        leads[4].action_set_won()
        leads[5].action_set_lost(lost_reason_id=lost_reason.id)

        self._travel_demo_register({f'trip_{key}': trip for key, trip in demo['trips'].items()})
        self._travel_demo_load_extra(demo)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'travel.trip',
            'view_mode': 'kanban,list,form',
            'name': self.env._("Trips"),
        }
