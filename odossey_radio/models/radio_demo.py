import base64
import io
import wave
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import Command, fields, models
from odoo.exceptions import UserError

DEMO_MODULE = 'odossey_radio_demo'


class RadioProgram(models.Model):
    _inherit = 'radio.program'

    # ------------------------------------------------------------------
    # Demo data on demand (Radio > Configuration > Settings > Load Demo Data)
    # FM station of Córdoba (Argentina), Responsable Inscripto: grid of programs, rate card,
    # advertisers and agencies, contracts in every situation, materials, the daily log of the
    # last month and the next week, invoices, commissions and opportunities.
    # ------------------------------------------------------------------
    @staticmethod
    def _radio_demo_cuit(prefix, number):
        digits = f"{prefix}{int(number):08d}"
        total = sum(int(d) * w for d, w in zip(digits, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
        check = 11 - total % 11
        return digits + str({11: 0, 10: 9}.get(check, check))

    @staticmethod
    def _radio_demo_audio(seconds=1):
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(b'\x00\x00' * 8000 * seconds)
        return base64.b64encode(buffer.getvalue())

    def _radio_demo_tax(self, vat_code='5'):
        return self.env['account.tax'].search([
            ('company_id', 'in', self.env.company.parent_ids.ids), ('type_tax_use', '=', 'sale'),
            ('tax_group_id.l10n_ar_vat_afip_code', '=', vat_code)], limit=1)

    def _radio_demo_partner(self, name, responsibility, vat, id_type='it_cuit', **vals):
        Partner = self.env['res.partner']
        partner = Partner.search([('vat', '=', vat)], limit=1)
        if partner:
            return partner
        values = {
            'name': name, 'vat': vat, 'is_company': id_type == 'it_cuit',
            'country_id': self.env.ref('base.ar').id,
            'state_id': self.env.ref('base.state_ar_x').id, 'city': vals.pop('city', "Córdoba"),
            'l10n_latam_identification_type_id': self.env.ref(f'l10n_ar.{id_type}').id,
            'l10n_ar_afip_responsibility_type_id': self.env.ref(f'l10n_ar.{responsibility}').id,
            'lang': 'es_AR' if self.env['res.lang']._lang_get('es_AR') else self.env.lang,
            'property_payment_term_id': self.env.ref(
                'account.account_payment_term_immediate', raise_if_not_found=False).id or False,
        }
        values.update(vals)
        return Partner.create(values)

    def _radio_demo_product(self, name, fmt, duration, price, daypart=None, program=None,
                            template=None, vat_code='5'):
        taxes = self._radio_demo_tax(vat_code)
        return self.env['product.product'].create({
            'name': name, 'type': 'service', 'radio_ok': True, 'sale_ok': True,
            'invoice_policy': 'delivery', 'subscribable': True,
            'subscription_template_id': (template or self.env.ref(
                'odossey_radio.template_monthly_fixed')).id,
            'radio_format_id': fmt.id, 'radio_duration': duration, 'list_price': price,
            'radio_daypart_id': daypart.id if daypart else False,
            'radio_program_id': program.id if program else False,
            'taxes_id': [Command.set(taxes.ids)], 'company_id': self.env.company.id,
        })

    def _radio_demo_order(self, partner, lines, start, template=None, **vals):
        """Advertising order confirmed -> contract. `lines`: (product, program, days, per day,
        quantity or None)."""
        order_lines = []
        for product, program, days, per_day, quantity in lines:
            line = {
                'product_id': product.id,
                'radio_program_id': program.id if program else False,
                'radio_weekday_ids': [Command.set(days.ids)],
                'radio_spots_per_day': per_day,
            }
            if quantity is not None:
                line['product_uom_qty'] = quantity
            order_lines.append(Command.create(line))
        values = {'partner_id': partner.id, 'radio_date_start': start, 'order_line': order_lines}
        values.update(vals)
        order = self.env['sale.order'].create(values)
        for line, (product, __, days, per_day, quantity) in zip(order.order_line, lines):
            if quantity is None:
                line.product_uom_qty = line._radio_monthly_estimate(1)
        return order

    def _radio_load_demo_data(self):
        company = self.env.company
        IMD = self.env['ir.model.data'].sudo()
        if IMD.search_count([('module', '=', DEMO_MODULE), ('name', '=', f'loaded_{company.id}')]):
            raise UserError(self.env._("The demo data is already loaded for %s.", company.name))
        if not company.chart_template or not company.chart_template.startswith('ar'):
            raise UserError(self.env._(
                "The demo data needs a company with the Argentinian chart of accounts."))
        today = fields.Date.context_today(self)
        start = today.replace(day=1) - relativedelta(months=1)       # first day of last month
        company.write({
            'radio_frequency': "FM 98.3 MHz", 'radio_signal': "LRJ 983",
            'radio_license': "Res. 1234/2019", 'radio_band': 'fm',
            'radio_enacom_category': 'c', 'radio_suspend_days': 30,
        })
        ref = self.env.ref
        days = {code: ref(f'odossey_radio.weekday_{code}') for code in
                ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')}
        weekdays = days['mon'] | days['tue'] | days['wed'] | days['thu'] | days['fri']
        weekend = days['sat'] | days['sun']
        every_day = weekdays | weekend
        central, afternoon, night = (ref('odossey_radio.daypart_morning'),
                                     ref('odossey_radio.daypart_afternoon'),
                                     ref('odossey_radio.daypart_night'))
        f_spot, f_mention, f_pnt, f_sponsor, f_digital = (
            ref('odossey_radio.format_spot'), ref('odossey_radio.format_mention'),
            ref('odossey_radio.format_pnt'), ref('odossey_radio.format_sponsorship'),
            ref('odossey_radio.format_digital'))
        tpl_fixed, tpl_aired = (ref('odossey_radio.template_monthly_fixed'),
                                ref('odossey_radio.template_monthly_aired'))

        # ------------------------------------------------------------------ hosts & grid
        Partner = self.env['res.partner']
        def host(name, dni):
            return Partner.search([('vat', '=', dni)], limit=1) or Partner.create({
                'name': name, 'vat': dni, 'radio_is_host': True,
                'country_id': ref('base.ar').id, 'city': "Córdoba",
                'l10n_latam_identification_type_id': ref('l10n_ar.it_dni').id})
        hosts = {
            'lucia': host("Lucía Ferreyra", '30111222'), 'martin': host("Martín Bustos", '28333444'),
            'carla': host("Carla Oviedo", '33555666'), 'nico': host("Nicolás Rivarola", '31777888'),
            'pablo': host("Pablo Ceballos", '27999000'), 'sole': host("Soledad Luna", '35123456'),
        }
        grid = [
            ('morning', "Despertate con la 98", 'news', weekdays, 6, 9, hosts['martin'] | hosts['lucia']),
            ('magazine', "La Mañana de Córdoba", 'magazine', weekdays, 9, 13, hosts['lucia'] | hosts['carla']),
            ('sports', "Mediodía Deportivo", 'sports', weekdays, 13, 14, hosts['nico']),
            ('afternoon', "Tarde Libre", 'magazine', weekdays, 14, 18, hosts['carla']),
            ('drive', "Regreso a Casa", 'music', weekdays, 18, 20, hosts['pablo']),
            ('folk', "Noche de Folclore", 'music', weekdays, 21, 24, hosts['sole']),
            ('saturday', "Sábado en Familia", 'entertainment', days['sat'], 9, 13, hosts['carla'] | hosts['pablo']),
            ('football', "Fútbol de Primera", 'sports', days['sun'], 15, 19, hosts['nico']),
            ('rock', "Clásicos del Rock", 'music', weekend, 20, 24, hosts['pablo']),
        ]
        programs = {}
        for key, name, genre, program_days, start_h, end_h, program_hosts in grid:
            programs[key] = self.create({
                'name': name, 'genre': genre, 'weekday_ids': [Command.set(program_days.ids)],
                'hour_from': start_h, 'hour_to': end_h,
                'host_ids': [Command.set(program_hosts.ids)],
                'audience': "12.000 oyentes estimados" if key in ('morning', 'magazine') else False,
            })
        all_programs = self.browse([p.id for p in programs.values()])
        all_programs.action_generate_breaks()
        programs['sports'].break_ids.write({'capacity': 120})    # short show, short breaks

        # ------------------------------------------------------------------ rate card
        product = self._radio_demo_product
        p_central = product("Spot 30\" central (06-13)", f_spot, 30, 7500, daypart=central)
        p_afternoon = product("Spot 30\" tarde (13-20)", f_spot, 30, 5500, daypart=afternoon)
        p_night = product("Spot 30\" noche (20-24)", f_spot, 30, 3500, daypart=night)
        p_spot_aired = product("Spot 20\" rotativo (por salida emitida)", f_spot, 20, 3800,
                               template=tpl_aired)
        p_official = product("Spot institucional 30\" (por salida emitida)", f_spot, 30, 6000,
                             template=tpl_aired)
        p_mention = product("Mención en vivo 20\"", f_mention, 20, 6000)
        p_pnt = product("PNT / publinota 60\"", f_pnt, 60, 25000)
        p_sponsor = product("Auspicio de programa (mensual)", f_sponsor, 10, 450000)
        p_football = product("Auspicio transmisión de fútbol (mensual)", f_sponsor, 10, 600000,
                             program=programs['football'])
        p_digital = product("Pack streaming + redes (mensual)", f_digital, 0, 120000)

        # ------------------------------------------------------------------ advertisers
        cuit = self._radio_demo_cuit
        agency_1 = self._radio_demo_partner("Agencia Creativa Mediterránea S.A.", 'res_IVARI',
                                            cuit(30, 71555111), radio_is_agency=True,
                                            radio_agency_commission=15.0,
                                            email="medios@creativamediterranea.example.com")
        agency_2 = self._radio_demo_partner("Grupo Medios Centro S.R.L.", 'res_IVARI',
                                            cuit(30, 71666222), radio_is_agency=True,
                                            radio_agency_commission=20.0,
                                            email="compras@grupomedioscentro.example.com")
        adv = {
            'cars': self._radio_demo_partner("Autos del Centro S.A.", 'res_IVARI', cuit(30, 70999333),
                                             radio_is_advertiser=True, radio_brand="Autos del Centro",
                                             radio_default_agency_id=agency_1.id),
            'market': self._radio_demo_partner("Supermercado El Trébol S.R.L.", 'res_IVARI',
                                               cuit(30, 71222444), radio_is_advertiser=True,
                                               radio_brand="El Trébol",
                                               email="marketing@eltrebol.example.com"),
            'bakery': self._radio_demo_partner("Panadería La Espiga", 'res_RM', cuit(27, 25444555),
                                               radio_is_advertiser=True, is_company=False,
                                               email="laespiga@example.com"),
            'pharmacy': self._radio_demo_partner("Farmacia San Martín S.R.L.", 'res_IVARI',
                                                 cuit(30, 71333555), radio_is_advertiser=True),
            'winery': self._radio_demo_partner("Bodega Los Andes S.A.", 'res_IVARI', cuit(30, 70888666),
                                               radio_is_advertiser=True, radio_brand="Vinos Los Andes",
                                               radio_default_agency_id=agency_2.id),
            'town': self._radio_demo_partner("Municipalidad de Villa Allende", 'res_IVAE',
                                             cuit(30, 99912345), radio_is_advertiser=True,
                                             email="prensa@villaallende.example.gob.ar"),
            'grill': self._radio_demo_partner("Parrilla Don Pepe", 'res_RM', cuit(20, 22777888),
                                              radio_is_advertiser=True, is_company=False),
            'gym': self._radio_demo_partner("Gimnasio Fuerza Vital", 'res_RM', cuit(20, 30888999),
                                            radio_is_advertiser=True, is_company=False),
            'estate': self._radio_demo_partner("Inmobiliaria Horizonte S.A.", 'res_IVARI',
                                               cuit(30, 71444666), radio_is_advertiser=True),
        }

        # ------------------------------------------------------------------ orders -> contracts
        order = self._radio_demo_order
        orders = {
            'cars': order(adv['cars'], [
                (p_central, programs['morning'], weekdays, 2, None),
                (p_afternoon, programs['afternoon'], weekdays, 2, None),
            ], start, radio_agency_id=agency_1.id, radio_bill_to='agency', radio_commission=15.0,
                radio_commission_mode='discount', radio_campaign="Lanzamiento SUV 2027",
                radio_op_number="OP-CM-2291"),
            'market': order(adv['market'], [
                (p_spot_aired, False, every_day, 3, None),
            ], start, radio_campaign="Ofertas del mes"),
            'bakery': order(adv['bakery'], [
                (p_mention, programs['magazine'], weekdays, 1, None),
            ], start, radio_date_end=today + timedelta(days=20)),
            'pharmacy': order(adv['pharmacy'], [
                (p_central, programs['magazine'], weekdays, 1, None),
                (p_pnt, programs['magazine'], days['wed'], 1, None),
            ], start, radio_campaign="Vacunación antigripal"),
            'winery': order(adv['winery'], [
                (p_sponsor, programs['folk'], weekdays, 1, 1),
                (p_night, programs['folk'], weekdays, 2, None),
            ], start, radio_agency_id=agency_2.id, radio_bill_to='advertiser', radio_commission=20.0,
                radio_commission_mode='bill', radio_campaign="Vendimia en la radio"),
            'town': order(adv['town'], [
                (p_official, False, weekdays, 2, None),
            ], start, radio_is_official=True, radio_official_body="Municipalidad de Villa Allende",
                radio_campaign="Campaña de reciclado", radio_op_number="OP-MVA-045/2026"),
            'grill': order(adv['grill'], [
                (p_mention, programs['drive'], days['thu'] | days['fri'], 1, None),
            ], start, radio_is_barter=True, radio_barter_note="Cenas para el equipo de la radio"),
            'gym': order(adv['gym'], [
                (p_afternoon, programs['drive'], weekdays, 1, None),
                (p_digital, False, weekdays, 0, 1),
            ], start),
            'football': order(adv['cars'], [
                (p_football, programs['football'], days['sun'], 2, 1),
            ], start, radio_agency_id=agency_1.id, radio_bill_to='agency', radio_commission=15.0,
                radio_campaign="Autos del Centro en el fútbol"),
        }
        for key, sale_order in orders.items():
            sale_order.action_confirm()
        contracts = {key: o.subscription_ids[:1] for key, o in orders.items()}
        contracts['grill'].radio_barter_invoice = False
        # quotation not confirmed yet
        self._radio_demo_order(adv['estate'], [(p_central, programs['morning'], weekdays, 1, None),
                                               (p_digital, False, weekdays, 0, 1)],
                               today + timedelta(days=5), radio_campaign="Nuevo loteo Horizonte")

        # ------------------------------------------------------------------ materials
        audio = self._radio_demo_audio()
        Material = self.env['radio.material']
        for key, contract in contracts.items():
            fmt_kinds = set(contract.sale_subscription_line_ids.radio_format_id.mapped('kind'))
            if fmt_kinds & {'spot', 'micro'}:
                Material.create({
                    'name': f"Spot {contract.partner_id.name} v1", 'subscription_id': contract.id,
                    'kind': 'audio', 'format_id': f_spot.id, 'audio_file': audio,
                    'audio_filename': 'spot_v1.wav', 'duration': 30, 'date_from': start,
                    'state': 'approved', 'sequence': 1,
                    'restriction': {'pharmacy': 'health', 'winery': 'alcohol'}.get(key, 'none'),
                    'authorization_ref': {'pharmacy': "ANMAT 5521/2026",
                                          'winery': "Ley 24.788 - mayores de 18"}.get(key, False),
                })
            if fmt_kinds & {'mention', 'pnt', 'sponsorship'}:
                Material.create({
                    'name': f"Guion {contract.partner_id.name}", 'subscription_id': contract.id,
                    'kind': 'script', 'format_id': False,
                    'script': f"<p>Este espacio llega gracias a <b>{contract.partner_id.name}</b>. "
                              f"Visitalos en Córdoba.</p>",
                    'duration': 20, 'date_from': start, 'state': 'approved',
                })
        # second version of the market spot (rotation) and one material to approve
        Material.create({'name': "Spot El Trébol v2 (fin de semana)",
                         'subscription_id': contracts['market'].id, 'kind': 'audio',
                         'format_id': f_spot.id, 'audio_file': audio, 'audio_filename': 'v2.wav',
                         'duration': 20, 'date_from': start, 'state': 'approved', 'sequence': 2})
        Material.create({'name': "Spot Autos del Centro - promo octubre",
                         'subscription_id': contracts['cars'].id, 'kind': 'audio',
                         'format_id': f_spot.id, 'duration': 30,
                         'date_from': today + timedelta(days=4), 'state': 'draft'})

        # ------------------------------------------------------------------ daily log
        all_contracts = self.env['sale.subscription'].browse([c.id for c in contracts.values()])
        all_contracts._radio_plan(start, today + timedelta(days=7))
        past = self.env['radio.emission'].search([('subscription_id', 'in', all_contracts.ids),
                                                  ('date', '<', today), ('state', '=', 'planned')])
        for index, emission in enumerate(past):
            emission.write({'state': 'aired', 'aired_at': emission.planned_datetime})
        # some exceptions: not aired (football match delayed), one rescheduled
        missed = past.filtered(lambda e: e.subscription_id == contracts['market'])[:3]
        missed.write({'state': 'missed', 'aired_at': False,
                      'note': "Cadena nacional / partido demorado"})
        missed[:1].action_compensate()

        # ------------------------------------------------------------------ invoicing
        invoiced = self.env['account.move']
        fixed = [c for k, c in contracts.items() if c.template_id == tpl_fixed and k != 'grill']
        for contract in fixed:                       # month 1 (last month)
            contract.recurring_next_date = start
            invoiced |= contract.generate_invoice()
        for contract in [c for c in contracts.values() if c.template_id == tpl_aired]:
            contract.recurring_next_date = start + relativedelta(months=1)
            invoiced |= contract.generate_invoice()  # aired spots of last month
        for contract in fixed:                       # month 2 (this month)
            invoiced |= contract.generate_invoice()
        contracts['grill'].recurring_next_date = start
        contracts['grill'].generate_invoice()        # barter: not invoiced
        # payments: everybody paid last month except the gym
        for invoice in invoiced.filtered(lambda m: m.state == 'posted' and m.invoice_date < today.replace(day=1)
                                         and m.partner_id != adv['gym']):
            self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=invoice.ids).create({})._create_payments()
        # overdue gym -> the credit control suspends its airing
        all_contracts._cron_radio_credit_control()
        # agency commission settlement of last month (Bodega Los Andes via Grupo Medios Centro)
        settle = self.env['radio.commission.settle'].create({
            'date_from': start, 'date_to': start + relativedelta(months=1, days=-1)})
        try:
            settle.action_settle()
        except UserError:
            pass
        # renewal activity of the contract ending soon
        all_contracts._cron_radio_renewals()

        # ------------------------------------------------------------------ CRM
        stages = self.env['crm.stage'].search([], order='sequence')
        self.env['crm.lead'].create([
            {'name': "Concesionaria: campaña fin de año", 'type': 'opportunity',
             'partner_id': adv['cars'].id, 'expected_revenue': 2400000,
             'stage_id': stages[1:2].id or stages[:1].id},
            {'name': "Inmobiliaria Horizonte: nuevo loteo", 'type': 'opportunity',
             'partner_id': adv['estate'].id, 'expected_revenue': 900000,
             'stage_id': stages[2:3].id or stages[:1].id},
            {'name': "Colegio San José: inscripciones 2027", 'type': 'opportunity',
             'contact_name': "Mónica Luque", 'email_from': "inscripciones@sanjose.example.com",
             'expected_revenue': 350000, 'stage_id': stages[:1].id},
        ])
        IMD.create({'module': DEMO_MODULE, 'name': f'loaded_{company.id}', 'model': 'res.company',
                    'res_id': company.id, 'noupdate': True})
        return {
            'type': 'ir.actions.act_window', 'res_model': 'sale.subscription',
            'name': self.env._("Advertising Contracts"), 'view_mode': 'kanban,list,form',
            'domain': [('radio_contract', '=', True)],
        }
