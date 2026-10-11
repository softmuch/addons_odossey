import base64
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, HttpCase, TransactionCase, new_test_user, tagged

# 1x1 white PNG used as a handwritten signature
SIGNATURE = base64.b64encode(bytes.fromhex(
    '89504e470d0a1a0a0000000d4948445200000001000000010806000000'
    '1f15c4890000000d49444154789c63f8ffff3f0005fe02fea7d6a5d40000000049454e44ae426082'))


@tagged('post_install', '-at_install')
class VetCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        ref = lambda x: cls.env.ref('odossey_veterinary.%s' % x)
        cls.ref = staticmethod(ref)
        cls.vet = new_test_user(cls.env, login='vet_test', groups='odossey_veterinary.group_vet_veterinarian',
                                name="Dra. Test")
        cls.vet.write({'vet_is_veterinarian': True, 'vet_license': 'MP 999'})
        cls.reception = new_test_user(cls.env, login='reception_test', groups='odossey_veterinary.group_vet_reception')
        cls.owner = cls.env['res.partner'].create({'name': "Ana Owner", 'email': 'ana@example.com',
                                                   'phone': '358 412 3456', 'country_id': cls.env.ref('base.ar').id})
        cls.dog = ref('species_dog')
        cls.cat = ref('species_cat')
        cls.pet = cls.env['vet.pet'].create({
            'name': "Firulais", 'owner_id': cls.owner.id, 'species_id': cls.dog.id, 'sex': 'male',
            'birthdate': fields.Date.today() - timedelta(days=400),
        })
        cls.vaccine = ref('product_vaccine_vanguard_plus_5_l4')
        cls.rabies = ref('product_vaccine_bagovac_rabia')
        cls.nexgard = ref('product_med_nexgard')
        cls.tramadol = ref('product_med_algen_tramadol')
        cls.synulox = ref('product_med_synulox')


class TestPet(VetCommon):

    def test_patient_basics(self):
        self.assertTrue(self.pet.ref.startswith('HC-'))
        self.assertIn(self.pet, self.owner.vet_pet_ids)
        self.assertIn(self.owner, self.env['res.partner'].search([('is_pet_owner', '=', True)]))
        self.assertNotIn(self.vet.partner_id, self.env['res.partner'].search([('is_pet_owner', '=', True)]))
        self.assertTrue(self.pet.age)
        self.env['vet.weight'].create({'pet_id': self.pet.id, 'weight': 12.5, 'date': fields.Date.today() - timedelta(days=30)})
        self.env['vet.weight'].create({'pet_id': self.pet.id, 'weight': 13.1})
        self.assertEqual(self.pet.weight, 13.1)

    def test_microchip_and_dates(self):
        with self.assertRaises(ValidationError):
            self.pet.microchip = '1234'
        self.pet.microchip = '999 000 111 222 333'
        self.assertEqual(self.pet.microchip, '999000111222333')
        with self.assertRaises(ValidationError):
            self.pet.birthdate = fields.Date.today() + timedelta(days=3)

    def test_breed_filtered_by_species_and_alerts(self):
        form = Form(self.env['vet.pet'])
        form.name = "Michi"
        form.owner_id = self.owner
        form.species_id = self.dog
        form.breed_id = self.ref('breed_dog_labrador')
        form.species_id = self.cat
        self.assertFalse(form.breed_id)
        self.pet.alert_ids = [(4, self.ref('alert_bites').id)]
        self.assertTrue(self.pet.has_danger_alert)
        self.assertIn(self.pet, self.env['vet.pet'].search([('has_danger_alert', '=', True)]))


class TestPreventive(VetCommon):

    def test_primary_course_and_booster(self):
        today = fields.Date.today()
        dose1 = self.env['vet.vaccination'].create({'pet_id': self.pet.id, 'product_id': self.vaccine.id,
                                                    'date': today - timedelta(days=21)})
        self.assertEqual(dose1.dose_number, 1)
        self.assertEqual(dose1.next_date, dose1.date + timedelta(weeks=3))   # 2 initial doses, 3 weeks apart
        dose2 = self.env['vet.vaccination'].create({'pet_id': self.pet.id, 'product_id': self.vaccine.id, 'date': today})
        self.assertEqual(dose2.dose_number, 2)
        self.assertTrue(dose1.superseded)
        self.assertEqual(dose1.state, 'done')
        self.assertEqual(dose2.next_date, today + relativedelta(months=12))
        self.assertEqual(dose2.state, 'up_to_date')
        self.assertEqual(self.pet.vaccination_state, 'up_to_date')

    def test_overdue_due_soon_and_search(self):
        today = fields.Date.today()
        rabies = self.env['vet.vaccination'].create({'pet_id': self.pet.id, 'product_id': self.rabies.id,
                                                     'date': today - timedelta(days=400)})
        self.assertEqual(rabies.state, 'overdue')
        self.assertEqual(self.pet.vaccination_state, 'overdue')
        self.assertIn(self.pet, self.env['vet.pet'].search([('vaccination_state', '=', 'overdue')]))
        self.assertIn(rabies, self.env['vet.vaccination'].search([('state', 'in', ['overdue'])]))
        flea = self.env['vet.vaccination'].create({'pet_id': self.pet.id, 'product_id': self.nexgard.id,
                                                   'date': today - timedelta(days=20)})
        self.assertEqual(flea.preventive_type, 'external')
        self.assertEqual(flea.next_date, flea.date + timedelta(days=30))
        self.assertEqual(flea.state, 'due_soon')

    def test_expired_lot_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['vet.vaccination'].create({'pet_id': self.pet.id, 'product_id': self.rabies.id,
                                                'expiration_date': fields.Date.today() - timedelta(days=1)})

    def test_reminders_grouped_by_owner(self):
        today = fields.Date.today()
        self.env['vet.vaccination'].create({'pet_id': self.pet.id, 'product_id': self.rabies.id, 'date': today - timedelta(days=360)})
        pet2 = self.env['vet.pet'].create({'name': "Luna", 'owner_id': self.owner.id, 'species_id': self.cat.id})
        self.env['vet.vaccination'].create({'pet_id': pet2.id, 'product_id': self.rabies.id, 'date': today - timedelta(days=362)})
        mails_before = self.env['mail.mail'].search_count([])
        self.env['vet.vaccination']._cron_send_reminders()
        mails = self.env['mail.mail'].search([], order='id desc', limit=self.env['mail.mail'].search_count([]) - mails_before)
        mine = mails.filtered(lambda m: self.owner in m.recipient_ids or 'ana@example.com' in (m.email_to or ''))
        self.assertEqual(len(mine), 1, "one email per owner, listing both pets")
        self.assertIn('Luna', mine.body_html)
        self.assertIn('Firulais', mine.body_html)
        # not sent twice
        self.env['vet.vaccination']._cron_send_reminders()
        self.assertEqual(self.env['mail.mail'].search_count([]), mails_before + len(mails))

    def test_whatsapp_link(self):
        action = self.pet.action_whatsapp_owner()
        self.assertTrue(action['url'].startswith('https://wa.me/5493584123456?text='))


class TestConsultation(VetCommon):

    def _consultation(self, **vals):
        return self.env['vet.consultation'].with_user(self.vet).create(dict({
            'pet_id': self.pet.id, 'vet_id': self.vet.id, 'reason': "Vaccination", 'weight': 14.2,
            'temperature': 40.1, 'line_ids': [(0, 0, {'product_id': self.ref('product_service_consult_general').id}),
                                              (0, 0, {'product_id': self.rabies.id})],
        }, **vals))

    def test_close_consultation(self):
        consultation = self._consultation()
        self.assertTrue(consultation.name.startswith('CON/'))
        self.assertIn('40.1', consultation.vitals_warning)
        consultation.action_start()
        consultation.action_done()
        self.assertEqual(consultation.state, 'done')
        self.assertEqual(self.pet.weight, 14.2)
        self.assertEqual(consultation.vaccination_ids.product_id, self.rabies)
        self.assertEqual(consultation.vaccination_ids.vet_id, self.vet)
        order = consultation.sale_order_id
        self.assertTrue(order)
        self.assertEqual(order.partner_id, self.owner)
        self.assertEqual(len(order.order_line), 2)
        with self.assertRaises(UserError):
            consultation.anamnesis = "<p>changed</p>"
        with self.assertRaises(UserError):
            consultation.unlink()

    def test_notifiable_warning_and_template(self):
        consultation = self._consultation(diagnosis_ids=[(6, 0, [self.ref('disease_leptospirosis').id])])
        self.assertIn('Notifiable', consultation.notifiable_warning)
        self.assertIn('Zoonosis', consultation.notifiable_warning)
        form = Form(self.env['vet.consultation'].with_user(self.vet))
        form.pet_id = self.pet
        form.template_id = self.ref('consultation_template_vaccination')
        self.assertEqual(form.consultation_type, 'vaccination')
        self.assertTrue(form.anamnesis)

    def test_reception_cannot_write_medical_record(self):
        consultation = self._consultation()
        consultation.with_user(self.reception).read(['name'])
        with self.assertRaises(AccessError):
            consultation.with_user(self.reception).write({'reason': "x"})
        with self.assertRaises(AccessError):
            self.env['vet.prescription'].with_user(self.reception).create({'pet_id': self.pet.id, 'vet_id': self.vet.id})

    def test_appointment_starts_consultation(self):
        event = self.env['calendar.event'].create({
            'vet_pet_id': self.pet.id, 'vet_appointment_type_id': self.ref('appointment_type_vaccination').id,
            'start': fields.Datetime.now(), 'user_id': self.vet.id, 'vet_reason': "Annual booster",
        })
        self.assertIn(self.owner, event.partner_ids)
        self.assertEqual(round((event.stop - event.start).total_seconds() / 60), 15)
        action = event.with_user(self.vet).action_vet_start_consultation()
        consultation = self.env['vet.consultation'].browse(action['res_id'])
        self.assertEqual(consultation.state, 'in_progress')
        self.assertEqual(consultation.consultation_type, 'vaccination')
        self.assertEqual(consultation.reason, "Annual booster")  # not the calendar's auto-generated description
        self.assertEqual(event.vet_state, 'in_consultation')
        self.assertIn(self.ref('product_service_vaccination'), consultation.line_ids.product_id)


class TestPrescription(VetCommon):

    def test_controlled_drug_requires_archived(self):
        rx = self.env['vet.prescription'].with_user(self.vet).create({
            'pet_id': self.pet.id, 'vet_id': self.vet.id,
            'line_ids': [(0, 0, {'product_id': self.tramadol.id, 'dose': "2 mg/kg"})],
        })
        self.assertEqual(rx.prescription_type, 'archived')
        with self.assertRaises(ValidationError):
            rx.prescription_type = 'simple'
        rx.action_issue()
        self.assertTrue(rx.name.startswith('RA/'))
        self.assertEqual(rx.content_hash, rx._compute_content_hash())
        with self.assertRaises(UserError):
            rx.notes = "changed"
        rx.cuve = "CUVE-123"  # the electronic code can still be recorded
        with self.assertRaises(UserError):
            rx.unlink()

    def test_issue_needs_license(self):
        self.vet.vet_license = False
        rx = self.env['vet.prescription'].create({
            'pet_id': self.pet.id, 'vet_id': self.vet.id,
            'line_ids': [(0, 0, {'product_id': self.synulox.id, 'dose': "1 tablet"})],
        })
        with self.assertRaises(UserError):
            rx.action_issue()

    def test_controlled_register(self):
        consultation = self.env['vet.consultation'].create({
            'pet_id': self.pet.id, 'vet_id': self.vet.id,
            'line_ids': [(0, 0, {'product_id': self.ref('product_med_ketamina').id})],
        })
        lines = self.env['vet.consultation.line'].search([('controlled', '=', True), ('consultation_id', '=', consultation.id)])
        self.assertEqual(len(lines), 1)


class TestHospitalization(VetCommon):

    def test_schedule_and_discharge(self):
        now = fields.Datetime.now()
        hosp = self.env['vet.hospitalization'].with_user(self.vet).create({
            'pet_id': self.pet.id, 'vet_id': self.vet.id, 'reason': "Gastroenteritis",
            'admission_date': now - timedelta(hours=30),
        })
        self.assertEqual(hosp.days, 2)
        self.env['vet.hospitalization.schedule.wizard'].create({
            'hospitalization_id': hosp.id, 'product_id': self.ref('product_med_cerenia').id,
            'start': now - timedelta(hours=24), 'every_hours': 8, 'duration_days': 2,
        }).action_schedule()
        self.assertEqual(len(hosp.task_ids), 6)
        past = hosp.task_ids.filtered(lambda t: t.scheduled_at <= now)
        past.action_done()
        self.assertEqual(past.done_by_id, self.vet)
        with self.assertRaises(ValidationError):
            self.env['vet.hospitalization'].create({'pet_id': self.pet.id, 'vet_id': self.vet.id, 'reason': "again"})
        hosp.action_discharge()
        self.assertEqual(hosp.state, 'discharged')
        self.assertFalse(hosp.task_ids.filtered(lambda t: t.state == 'pending'))
        lines = hosp.sale_order_id.order_line
        day = lines.filtered(lambda l: l.product_id == self.ref('product_service_hospitalization_day'))
        self.assertEqual(day.product_uom_qty, 2)
        cerenia = lines.filtered(lambda l: l.product_id == self.ref('product_med_cerenia'))
        self.assertEqual(len(cerenia), 1, "applications of the same product are grouped")
        self.assertEqual(cerenia.product_uom_qty, len(past))


class TestConsentLab(VetCommon):

    def test_consent_sign_and_lock(self):
        consent = self.env['vet.consent'].create({
            'pet_id': self.pet.id, 'template_id': self.ref('consent_template_surgery_anesthesia').id,
            'procedure': "Castration",
        })
        self.assertIn('Firulais', consent.content)
        self.assertIn('Ana Owner', consent.content)
        self.assertIn('Castration', consent.content)
        consent._sign("Ana Owner", SIGNATURE)
        self.assertEqual(consent.state, 'signed')
        self.assertEqual(consent.signature_hash, consent._get_signature_hash())
        with self.assertRaises(UserError):
            consent.content = "<p>other</p>"
        with self.assertRaises(UserError):
            consent.unlink()

    def test_lab_flags(self):
        result = self.env['vet.lab.result'].create({'pet_id': self.pet.id, 'panel_id': self.ref('lab_panel_biochem_basic').id})
        self.assertTrue(result.line_ids)
        creat = result.line_ids.filtered(lambda l: l.analyte_id == self.ref('lab_panel_biochem_basic_2'))
        creat.value = 3.0
        self.assertEqual(creat.flag, 'high')
        creat.value = 1.0
        self.assertEqual(creat.flag, 'normal')
        # numbers without trailing zeros and with the language's decimal separator
        self.assertEqual(creat.with_context(lang='en_US')._vet_format_number(1.025), '1.025')
        self.assertEqual(creat.with_context(lang='en_US')._vet_format_number(38.0), '38')
        self.assertNotIn('.000', creat.reference)

    def test_ui_details(self):
        # consent date rendered in the owner's language format, not ISO
        consent = self.env['vet.consent'].create({
            'pet_id': self.pet.id, 'template_id': self.ref('consent_template_surgery_anesthesia').id})
        self.assertNotIn(fields.Date.to_string(fields.Date.today()), consent.content)
        # travel certificate text follows the destination
        with Form(self.env['vet.certificate']) as form:
            form.pet_id = self.pet
            form.certificate_type = 'travel'
            form.destination = "Uruguay"
            self.assertIn("Uruguay", str(form.body))
        # clinical numbers are not summed when grouping
        for model, field in (('vet.vaccination', 'dose_number'), ('vet.consultation', 'temperature'), ('vet.pet', 'weight')):
            self.assertFalse(self.env[model]._fields[field].aggregator, field)
        # default hospitalization day service visible in Settings
        settings = self.env['res.config.settings'].create({})
        self.assertEqual(settings.vet_hospitalization_product_id, self.env['vet.hospitalization']._default_day_product())
        # product categories named in the clinic's language
        from odoo.addons.odossey_veterinary.hooks import localize_product_categories
        localize_product_categories(self.env, 'es_AR')
        self.assertEqual(self.ref('product_category_medications').name, "Medicamentos")


class TestDemoAndReports(VetCommon):

    def test_demo_and_reports(self):
        if not self.env['ir.config_parameter'].sudo().get_param('odossey_veterinary.demo_loaded'):
            self.env['vet.demo'].load_demo()
        self.assertGreaterEqual(self.env['vet.pet'].search_count([]), 10)
        with self.assertRaises(UserError):
            self.env['vet.demo'].load_demo()
        for xmlid, model in (('action_report_vaccination_card', 'vet.pet'), ('action_report_prescription', 'vet.prescription'),
                             ('action_report_consultation', 'vet.consultation'), ('action_report_consent', 'vet.consent'),
                             ('action_report_lab_result', 'vet.lab.result'), ('action_report_certificate', 'vet.certificate'),
                             ('action_report_discharge', 'vet.hospitalization')):
            records = self.env[model].search([], limit=2)
            self.assertTrue(records, model)
            report = self.ref(xmlid)
            html = report._render_qweb_html(report.report_name, records.ids)[0]
            self.assertTrue(html)


@tagged('post_install', '-at_install')
class TestPortal(HttpCase):

    def test_portal_owner_sees_only_own_pets(self):
        owner = self.env['res.partner'].create({'name': "Portal Owner", 'email': 'portal.owner@example.com'})
        other = self.env['res.partner'].create({'name': "Other Owner"})
        user = new_test_user(self.env, login='portal_owner', groups='base.group_portal', partner_id=owner.id, password='portal_owner')
        dog = self.env.ref('odossey_veterinary.species_dog')
        mine = self.env['vet.pet'].create({'name': "MiPerro", 'owner_id': owner.id, 'species_id': dog.id})
        theirs = self.env['vet.pet'].create({'name': "AjenoPerro", 'owner_id': other.id, 'species_id': dog.id})
        self.authenticate(user.login, 'portal_owner')
        page = self.url_open('/my/vet').text
        self.assertIn('MiPerro', page)
        self.assertNotIn('AjenoPerro', page)
        self.assertEqual(self.url_open('/my/vet/pets/%s' % mine.id).status_code, 200)
        response = self.url_open('/my/vet/pets/%s' % theirs.id)
        self.assertNotIn('AjenoPerro', response.text)
        # vaccination card and certificate downloads (report file name on vet.pet / vet.certificate)
        self.assertEqual(self.url_open('/my/vet/pets/%s/card' % mine.id).status_code, 200)
        cert = self.env['vet.certificate'].create({'pet_id': mine.id, 'certificate_type': 'health'})
        self.assertEqual(self.url_open('/my/vet/certificates/%s' % cert.id).status_code, 200)

    def test_actions_context_is_literal(self):
        """Window action contexts are evaluated in the browser: no server-side helpers such as ref()."""
        actions = self.env['ir.actions.act_window'].search([('res_model', 'like', 'vet.%')])
        actions |= self.env.ref('odossey_veterinary.vet_appointment_action') | self.env.ref('odossey_veterinary.vet_waiting_room_action')
        for action in actions:
            self.assertNotIn('ref(', action.context or '', action.xml_id)
