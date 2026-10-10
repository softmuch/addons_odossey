from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class VetDemo(models.AbstractModel):
    _name = 'vet.demo'
    _description = 'Veterinary Demo Data'

    def _ref(self, xmlid):
        return self.env.ref('odossey_veterinary.%s' % xmlid)

    def _product(self, xmlid):
        return self._ref(xmlid)

    @api.model
    def load_demo(self):
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Only administrators can load the demo data."))
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('odossey_veterinary.demo_loaded'):
            raise UserError(_("The demo data is already loaded."))
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()

        # ------------------------------------------------------------ veterinarians
        Users = self.env['res.users'].with_context(no_reset_password=True)
        vet_group = self._ref('group_vet_veterinarian')
        vets = self.env['res.users']
        for name, login, license_no in (("Dra. Laura Gómez", 'laura.gomez@vetsanroque.com.ar', 'MP 4521'),
                                        ("Dr. Martín Ferreyra", 'martin.ferreyra@vetsanroque.com.ar', 'MP 3877')):
            user = Users.search([('login', '=', login)], limit=1) or Users.create({
                'name': name, 'login': login, 'email': login,
                'group_ids': [(4, vet_group.id)],
            })
            user.write({'vet_is_veterinarian': True, 'vet_license': license_no,
                        'vet_college': "Colegio Médico Veterinario de la Provincia de Córdoba"})
            vets |= user
        admin = self.env.user
        if not admin.vet_is_veterinarian:
            admin.write({'vet_is_veterinarian': True, 'vet_license': admin.vet_license or 'MP 1001',
                         'vet_college': admin.vet_college or "Colegio Médico Veterinario de la Provincia de Córdoba"})
        laura, martin = vets[0], vets[1]

        # ------------------------------------------------------------ owners
        ar = self.env.ref('base.ar')
        langs = [code for code, _name in self.env['res.lang'].get_installed()]
        owner_lang = next((code for code in ('es_AR', 'es_419', 'es_ES') if code in langs), self.env.lang)
        owners = self.env['res.partner']
        for name, phone, email, street in (
                ("María Fernández", "+54 9 358 412-3456", "maria.fernandez@example.com", "Av. España 1234"),
                ("Juan Pérez", "+54 9 358 433-1122", "juan.perez@example.com", "Constitución 450"),
                ("Lucía Martínez", "+54 9 358 455-7788", "lucia.martinez@example.com", "Sobremonte 980"),
                ("Carlos Rodríguez", "+54 9 358 466-2211", "carlos.rodriguez@example.com", "Bv. Roca 1550"),
                ("Sofía Giménez", "+54 9 358 477-9900", "sofia.gimenez@example.com", "Alvear 320"),
                ("Familia López", "+54 9 358 488-6655", "lopez.familia@example.com", "Mitre 2100")):
            owners |= self.env['res.partner'].create({
                'name': name, 'phone': phone, 'email': email, 'street': street, 'city': "Río Cuarto",
                'zip': "5800", 'country_id': ar.id, 'lang': owner_lang,
            })
        maria, juan, lucia, carlos, sofia, lopez = owners

        # ------------------------------------------------------------ patients
        dog, cat = self._ref('species_dog'), self._ref('species_cat')
        Pet = self.env['vet.pet']

        def pet(name, owner, species, breed, sex, birth_months, weights, **kw):
            p = Pet.create(dict({
                'name': name, 'owner_id': owner.id, 'species_id': species.id,
                'breed_id': self._ref(breed).id if breed else False, 'sex': sex,
                'birthdate': today - relativedelta(months=birth_months),
            }, **kw))
            for months_ago, kg in weights:
                self.env['vet.weight'].create({'pet_id': p.id, 'weight': kg, 'date': today - relativedelta(months=months_ago)})
            return p

        firulais = pet("Firulais", maria, dog, 'breed_dog_mixed', 'male', 50, [(12, 17.5), (6, 18.2), (0, 18.9)],
                       neutered=True, coat="Marrón y blanco", microchip="032000123456789", temperament='calm')
        luna = pet("Luna", maria, cat, 'breed_cat_domestic', 'female', 30, [(8, 3.9), (1, 4.2)], neutered=True, coat="Atigrada")
        rocco = pet("Rocco", juan, dog, 'breed_dog_dogo_argentino', 'male', 36, [(10, 38.0), (2, 41.5)],
                    coat="Blanco", temperament='aggressive',
                    alert_ids=[(6, 0, [self._ref('alert_bites').id])],
                    handling_notes="Usar bozal antes de manipular. Más tranquilo con el tutor presente.")
        mora = pet("Mora", lucia, dog, 'breed_dog_french_bulldog', 'female', 20, [(6, 10.8), (0, 11.4)],
                   coat="Atigrado", alert_ids=[(6, 0, [self._ref('alert_brachycephalic').id])])
        simba = pet("Simba", carlos, cat, 'breed_cat_siamese', 'male', 4, [(1, 1.1), (0, 1.6)], coat="Seal point")
        toby = pet("Toby", carlos, dog, 'breed_dog_golden', 'male', 110, [(12, 33.0), (0, 31.2)],
                   neutered=True, coat="Dorado", alert_ids=[(6, 0, [self._ref('alert_cardiac').id])],
                   allergy_notes="Alergia a penicilinas", chronic_condition_ids=[(6, 0, [self._ref('disease_mmvd').id])])
        nala = pet("Nala", sofia, dog, 'breed_dog_labrador', 'female', 3, [(0, 7.8)], coat="Negro")
        michi = pet("Michi", sofia, cat, 'breed_cat_persian', 'female', 70, [(3, 4.8)], neutered=True, coat="Blanco")
        bruno = pet("Bruno", lopez, dog, 'breed_dog_german_shepherd', 'male', 60, [(4, 34.0), (0, 35.1)], coat="Negro y fuego")
        coco = pet("Coco", lopez, self._ref('species_rabbit'), False, 'female', 18, [(0, 2.1)], coat="Gris")

        # ------------------------------------------------------------ stock lots for vaccines and controlled drugs
        stock_loc = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1).lot_stock_id
        lots = {}
        for xmlid, lot_name, months in (('product_vaccine_vanguard_plus_5_l4', 'VG24A118', 14),
                                         ('product_vaccine_bagovac_rabia', 'BR25-0457', 10),
                                         ('product_vaccine_felocell_3', 'FC25B061', 12),
                                         ('product_vaccine_nobivac_puppy_dp_plus', 'NP25-332', 8),
                                         ('product_med_algen_tramadol', 'TR-2611', 18),
                                         ('product_med_ketamina', 'KT-0925', 20)):
            product = self._product(xmlid)
            lot = self.env['stock.lot'].create({
                'name': lot_name, 'product_id': product.id, 'company_id': self.env.company.id,
                'expiration_date': now + relativedelta(months=months),
            })
            if stock_loc:
                self.env['stock.quant']._update_available_quantity(product, stock_loc, 25, lot_id=lot)
            lots[xmlid] = lot

        # ------------------------------------------------------------ preventive history
        Vacc = self.env['vet.vaccination']

        def vacc(p, xmlid, days_ago, vet, dose=0):
            return Vacc.create({
                'pet_id': p.id, 'product_id': self._product(xmlid).id, 'date': today - timedelta(days=days_ago),
                'vet_id': vet.id, 'dose_number': dose, 'lot_id': lots.get(xmlid, self.env['stock.lot']).id,
                'lot_name': lots[xmlid].name if xmlid in lots else 'L-%s' % (1000 + days_ago),
            })

        vacc(firulais, 'product_vaccine_vanguard_plus_5_l4', 340, laura, 4)      # booster due soon
        vacc(firulais, 'product_vaccine_bagovac_rabia', 380, laura, 3)           # rabies overdue
        vacc(firulais, 'product_med_nexgard', 20, laura)                         # antiparasitic, due soon
        vacc(luna, 'product_vaccine_felocell_3', 120, martin, 3)                 # up to date
        vacc(luna, 'product_vaccine_bagovac_rabia', 120, martin, 2)
        vacc(rocco, 'product_vaccine_vanguard_plus_5_l4', 420, martin, 3)        # overdue
        vacc(mora, 'product_vaccine_vanguard_plus_5_l4', 60, laura, 3)
        vacc(mora, 'product_vaccine_bagovac_rabia', 60, laura, 1)
        vacc(mora, 'product_med_bravecto', 70, laura)
        vacc(simba, 'product_vaccine_felocell_3', 18, martin, 1)                 # kitten: 2nd dose due
        vacc(toby, 'product_vaccine_vanguard_plus_5_l4', 200, laura, 6)
        vacc(toby, 'product_vaccine_bagovac_rabia', 200, laura, 6)
        vacc(nala, 'product_vaccine_nobivac_puppy_dp_plus', 25, martin, 1)       # puppy: overdue next dose
        vacc(nala, 'product_med_drontal_plus', 25, martin)
        vacc(bruno, 'product_vaccine_vanguard_plus_5_l4', 300, martin, 5)
        vacc(bruno, 'product_vaccine_bagovac_rabia', 300, martin, 5)

        # ------------------------------------------------------------ closed consultations
        Consultation = self.env['vet.consultation']

        def consult(p, vet, days_ago, ctype, reason, vitals, diagnoses, lines, plan, **kw):
            c = Consultation.create(dict({
                'pet_id': p.id, 'vet_id': vet.id, 'consultation_type': ctype, 'reason': reason,
                'date': now - timedelta(days=days_ago, hours=2),
                'anamnesis': kw.pop('anamnesis', False), 'physical_exam': kw.pop('exam', False),
                'diagnosis_ids': [(6, 0, [self._ref(d).id for d in diagnoses])], 'plan': plan,
                'line_ids': [(0, 0, {'product_id': self._product(x).id, 'quantity': q,
                                     'lot_id': lots[x].id if x in lots else False}) for x, q in lines],
            }, **vitals, **kw))
            c.action_start()
            c.action_done()
            return c

        c_toby = consult(toby, laura, 40, 'consultation', "Tos y cansancio al caminar",
                         {'weight': 31.2, 'temperature': 38.6, 'heart_rate': 150, 'respiratory_rate': 34, 'mucous_membranes': 'pink', 'crt': 2.0},
                         ['disease_mmvd'], [('product_service_consult_general', 1), ('product_service_echocardiography', 1)],
                         "<p>Pimobendan 0,25 mg/kg c/12 h. Control ecocardiográfico en 3 meses.</p>",
                         anamnesis="<p>Tose de noche desde hace 2 semanas, se cansa en los paseos.</p>",
                         exam="<p>Soplo sistólico grado IV/VI en foco mitral.</p>",
                         follow_up_date=today + timedelta(days=50))
        consult(mora, laura, 60, 'vaccination', "Refuerzo anual",
                {'weight': 11.4, 'temperature': 38.7, 'heart_rate': 110, 'respiratory_rate': 24},
                [], [('product_service_vaccination', 1)], "<p>Vacunación anual aplicada.</p>")
        c_rocco = consult(rocco, martin, 10, 'emergency', "Herida por pelea",
                          {'weight': 41.5, 'temperature': 39.6, 'heart_rate': 120, 'respiratory_rate': 30, 'pain_score': '2'},
                          [], [('product_service_consult_emergency', 1), ('product_service_suture_simple', 1),
                               ('product_med_ketamina', 1)],
                          "<p>Sutura bajo sedación. Antibiótico y analgésico 7 días.</p>",
                          owner_instructions="<p>Collar isabelino 10 días. Volver a control en 7 días.</p>")

        # ------------------------------------------------------------ prescriptions
        Rx = self.env['vet.prescription']
        rx1 = Rx.create({
            'pet_id': toby.id, 'vet_id': laura.id, 'consultation_id': c_toby.id, 'diagnosis': "Enfermedad valvular mitral",
            'line_ids': [(0, 0, {'product_id': self._product('product_med_vetmedin').id, 'dose': "1 comp. 10 mg",
                                 'frequency': "c/12 h", 'duration_days': 90, 'quantity': 2})],
            'notes': "Administrar 1 hora antes de las comidas.",
        })
        rx1.action_issue()
        rx2 = Rx.create({
            'pet_id': rocco.id, 'vet_id': martin.id, 'consultation_id': c_rocco.id, 'diagnosis': "Herida por mordedura",
            'line_ids': [
                (0, 0, {'product_id': self._product('product_med_synulox').id, 'dose': "1 comp. 500 mg", 'frequency': "c/12 h",
                        'duration_days': 7, 'quantity': 1}),
                (0, 0, {'product_id': self._product('product_med_algen_tramadol').id, 'dose': "2 mg/kg", 'frequency': "c/12 h",
                        'duration_days': 5, 'quantity': 1}),
            ],
            'rve_state': 'pending',
        })
        rx2.action_issue()

        # ------------------------------------------------------------ hospitalization (admitted)
        hosp = self.env['vet.hospitalization'].create({
            'pet_id': bruno.id, 'vet_id': martin.id, 'reason': "Gastroenteritis aguda, deshidratación moderada",
            'cage': "Canil 2", 'admission_date': now - timedelta(hours=20), 'diet': "Ayuno 12 h, luego dieta gastrointestinal",
        })
        self.env['vet.hospitalization.schedule.wizard'].create({
            'hospitalization_id': hosp.id, 'kind': 'fluids', 'product_id': self._product('product_med_ringer_lactato').id,
            'dose': "60 ml/kg/día", 'start': now - timedelta(hours=18), 'every_hours': 6, 'duration_days': 2,
        }).action_schedule()
        self.env['vet.hospitalization.schedule.wizard'].create({
            'hospitalization_id': hosp.id, 'kind': 'medication', 'product_id': self._product('product_med_cerenia').id,
            'dose': "1 mg/kg SC", 'start': now - timedelta(hours=18), 'every_hours': 24, 'duration_days': 3,
        }).action_schedule()
        self.env['vet.hospitalization.schedule.wizard'].create({
            'hospitalization_id': hosp.id, 'kind': 'vitals', 'name': "Control de signos vitales",
            'start': now - timedelta(hours=18), 'every_hours': 8, 'duration_days': 2,
        }).action_schedule()
        for task in hosp.task_ids.filtered(lambda t: t.scheduled_at < now - timedelta(hours=2)):
            task.write({'state': 'done', 'done_at': task.scheduled_at + timedelta(minutes=10), 'done_by_id': martin.id,
                        'temperature': 38.9 if task.task_type == 'vitals' else 0})

        # ------------------------------------------------------------ lab result with abnormal values
        lab = self.env['vet.lab.result'].create({
            'pet_id': bruno.id, 'panel_id': self._ref('lab_panel_biochem_basic').id, 'laboratory': "Laboratorio interno",
        })
        values = {'Urea (BUN)': 38.0, 'Creatinine': 1.4, 'ALT (GPT)': 85.0, 'ALP': 120.0, 'Glucose': 98.0, 'Total protein': 7.9}
        for line in lab.line_ids:
            line.value = values.get(line.analyte_id.with_context(lang='en_US').name, 0)
        lab.write({'state': 'done', 'conclusion': "Urea elevada compatible con deshidratación."})

        # ------------------------------------------------------------ consents and certificate
        self.env['vet.consent'].create({
            'pet_id': nala.id, 'template_id': self._ref('consent_template_surgery_anesthesia').id,
            'procedure': "Ovariohisterectomía", 'vet_id': laura.id,
        })
        self.env['vet.certificate'].create({
            'pet_id': firulais.id, 'certificate_type': 'travel', 'destination': "Uruguay", 'vet_id': laura.id,
            'valid_until': today + timedelta(days=10),
        })

        # ------------------------------------------------------------ today's agenda
        Event = self.env['calendar.event']
        day_start = datetime.combine(today, time(12, 0))  # 9:00 Argentina (UTC-3)
        for hours, p, atype, vet, state in ((0, luna, 'appointment_type_consultation', laura, 'arrived'),
                                            (0.5, firulais, 'appointment_type_vaccination', laura, 'confirmed'),
                                            (1, simba, 'appointment_type_vaccination', martin, 'booked'),
                                            (2, toby, 'appointment_type_followup', laura, 'booked'),
                                            (3, nala, 'appointment_type_surgery', martin, 'booked')):
            start = day_start + timedelta(hours=hours)
            atype_rec = self._ref(atype)
            Event.create({
                'vet_pet_id': p.id, 'vet_appointment_type_id': atype_rec.id, 'start': start,
                'stop': start + timedelta(minutes=atype_rec.duration), 'user_id': vet.id, 'vet_state': state,
                'vet_room_id': self._ref('vet_room_surgery' if atype == 'appointment_type_surgery' else 'vet_room_consulting_1').id,
            })
        ICP.set_param('odossey_veterinary.demo_loaded', fields.Datetime.to_string(now))
        return True
