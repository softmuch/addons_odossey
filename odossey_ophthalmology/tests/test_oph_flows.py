import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

SIGNATURE = base64.b64encode(base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='))


class OphCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, no_mail_to_attendees=True))
        ref = lambda x: cls.env.ref('odossey_ophthalmology.%s' % x)
        cls.ref = staticmethod(ref)
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.doctor = Users.create({
            'name': "Dra. Test", 'login': 'oph.doctor.test', 'email': 'doctor@test.example',
            'group_ids': [(4, ref('group_oph_ophthalmologist').id)],
            'oph_is_ophthalmologist': True, 'oph_license': 'MN 1234',
        })
        cls.reception = Users.create({
            'name': "Recepción Test", 'login': 'oph.reception.test', 'email': 'reception@test.example',
            'group_ids': [(4, ref('group_oph_reception').id)],
        })
        cls.insurance = cls.env['oph.insurance'].create({'name': "Obra Social Test", 'short_name': 'OST'})
        cls.consult = ref('product_cons_1v')
        cls.oct = ref('product_oct_mac')
        cls.env['oph.insurance.price'].create({
            'insurance_id': cls.insurance.id, 'product_id': cls.consult.product_tmpl_id.id, 'nomenclator_code': '420101',
            'insurance_amount': 30000, 'copay_amount': 5000,
        })
        cls.patient = cls.env['res.partner'].create({
            'name': "Paciente Test", 'is_oph_patient': True, 'oph_document': '30.111.222', 'oph_birthdate': '1960-01-01',
            'email': 'patient@test.example', 'phone': '11 4567-8901', 'country_id': cls.env.ref('base.ar').id,
            'oph_insurance_id': cls.insurance.id, 'oph_member_number': '123-45',
        })
        cls.private = cls.env['res.partner'].create({'name': "Particular Test", 'is_oph_patient': True})
        cls.glaucoma = ref('diagnosis_h40_1')

    def _exam(self, patient=None, **vals):
        values = {'patient_id': (patient or self.patient).id, 'doctor_id': self.doctor.id,
                  'diagnosis_ids': [(0, 0, {'diagnosis_id': self.glaucoma.id, 'eye': 'ou'})]}
        values.update(vals)
        return self.env['oph.exam'].create(values)


class TestPatientAndAgenda(OphCommon):

    def test_patient_record_number_and_alerts(self):
        self.assertTrue(self.patient.oph_record_number.startswith('HC-'))
        self.assertTrue(self.patient.oph_age >= 60)
        self.patient.write({'oph_anticoagulated': True,
                            'oph_allergy_ids': [(4, self.ref('allergy_penicillin').id)]})
        self.assertEqual(self.patient.oph_alert_level, 'danger')
        self.assertIn('Penicillin', str(self.patient.oph_alert_html))
        partner = self.env['res.partner'].create({'name': "Contacto"})
        self.assertFalse(partner.oph_record_number)
        partner.is_oph_patient = True
        self.assertTrue(partner.oph_record_number)
        with self.assertRaises(ValidationError):
            partner.oph_birthdate = fields.Date.today() + timedelta(days=2)

    def test_appointment_flow(self):
        atype = self.ref('appointment_type_primera_vez')
        start = fields.Datetime.now() + timedelta(hours=1)
        event = self.env['calendar.event'].create({
            'oph_patient_id': self.patient.id, 'oph_appointment_type_id': atype.id, 'start': start,
            'user_id': self.doctor.id, 'oph_reason': "Visión borrosa",
        })
        self.assertIn(self.patient, event.partner_ids)
        self.assertEqual(event.oph_insurance_id, self.insurance)
        self.assertEqual(event.stop, start + timedelta(minutes=atype.duration))
        self.assertTrue(event.is_oph_appointment)
        event.action_oph_arrived()
        self.assertEqual(event.oph_state, 'arrived')
        self.assertTrue(event.oph_arrival_time)
        action = event.with_user(self.doctor).action_oph_start_consultation()
        exam = self.env['oph.exam'].browse(action['res_id'])
        self.assertEqual(exam.state, 'in_progress')
        self.assertEqual(exam.reason, "Visión borrosa")
        self.assertEqual(exam.doctor_id, self.doctor)
        self.assertIn(atype.product_id, exam.line_ids.product_id)
        self.assertEqual(event.oph_state, 'in_consultation')

    def test_waiting_room_drag_sets_arrival(self):
        event = self.env['calendar.event'].create({
            'oph_patient_id': self.patient.id, 'start': fields.Datetime.now(),
            'stop': fields.Datetime.now() + timedelta(minutes=20)})
        event.write({'oph_state': 'dilating'})
        self.assertTrue(event.oph_arrival_time)

    def test_whatsapp_number(self):
        self.assertEqual(self.patient._oph_whatsapp_number(), '5491145678901')
        action = self.patient.action_oph_whatsapp_control()
        self.assertTrue(action['url'].startswith('https://wa.me/5491145678901'))


class TestExam(OphCommon):

    def test_validation_and_warnings(self):
        exam = self._exam(iop_od=26, iop_os=15)
        self.assertTrue(exam.iop_warning)
        with self.assertRaises(ValidationError):
            exam.rx_axis_od = 190
        with self.assertRaises(ValidationError):
            exam.cup_disc_os = 1.5

    def test_close_lock_addendum_and_control(self):
        exam = self._exam()
        exam.action_start()
        no_diag = self.env['oph.exam'].create({'patient_id': self.patient.id, 'doctor_id': self.doctor.id})
        no_diag.action_start()
        with self.assertRaises(UserError):
            no_diag.action_done()
        exam.action_done()
        self.assertEqual(exam.state, 'done')
        self.assertTrue(exam.next_control_date > fields.Date.today())
        with self.assertRaises(UserError):
            exam.iop_od = 30
        with self.assertRaises(UserError):
            exam.unlink()
        exam.addendum_ids = [(0, 0, {'note': "Se agrega resultado de campo visual."})]
        self.assertEqual(len(exam.addendum_ids), 1)
        with self.assertRaises(UserError):
            exam.addendum_ids.note = "cambio"
        self.assertEqual(self.patient.oph_next_control_date, exam.next_control_date)

    def test_billing_insurance_and_private(self):
        exam = self._exam(line_ids=[(0, 0, {'product_id': self.consult.id}), (0, 0, {'product_id': self.oct.id})])
        exam.action_start()
        exam.action_done()
        claim = exam.claim_ids
        self.assertEqual(len(claim), 1)
        self.assertEqual(claim.amount, 30000)
        self.assertEqual(claim.nomenclator_code, '420101')
        self.assertEqual(claim.member_number, '123-45')
        order = exam.sale_order_ids
        self.assertEqual(len(order), 1)
        self.assertEqual(order.partner_id, self.patient)
        prices = sorted(order.order_line.mapped('price_unit'))
        self.assertIn(5000, prices)  # co-payment of the covered consultation
        self.assertEqual(len(order.order_line), 2)  # + OCT, not covered → private price
        # private patient: everything goes to the quotation
        private = self._exam(patient=self.private, line_ids=[(0, 0, {'product_id': self.consult.id})])
        private.action_start()
        private.action_done()
        self.assertFalse(private.claim_ids)
        self.assertEqual(len(private.sale_order_ids.order_line), 1)
        # already billed lines are not billed twice
        private.action_create_billing()
        self.assertEqual(len(private.sale_order_ids), 1)

    def test_copy_previous_and_glasses(self):
        first = self._exam(rx_sph_od=-2.0, rx_cyl_od=-0.5, rx_axis_od=90, macula_od="Normal")
        first.action_start()
        first.action_done()
        second = self.env['oph.exam'].create({'patient_id': self.patient.id, 'doctor_id': self.doctor.id})
        second.action_copy_previous()
        self.assertEqual(second.lenso_sph_od, -2.0)
        self.assertEqual(second.macula_od, "Normal")
        self.assertEqual(second.diagnosis_ids.diagnosis_id, self.glaucoma)
        action = first.action_create_glasses()
        glasses = self.env['oph.glasses.prescription'].browse(action['res_id'])
        self.assertEqual(glasses.sph_od, -2.0)
        self.assertEqual(glasses.axis_od, 90)

    def test_access_log(self):
        exam = self._exam()
        exam.with_user(self.doctor).web_read({'name': {}})
        log = self.env['oph.access.log'].search([('res_id', '=', exam.id), ('res_model', '=', 'oph.exam')])
        self.assertEqual(log.user_id, self.doctor)
        self.assertEqual(log.patient_id, self.patient)


class TestDocuments(OphCommon):

    def test_glasses_issue_and_lock(self):
        glasses = self.env['oph.glasses.prescription'].create({'patient_id': self.patient.id, 'doctor_id': self.doctor.id,
                                                              'sph_od': -1.5, 'sph_os': -1.25})
        glasses.action_issue()
        self.assertEqual(glasses.state, 'issued')
        self.assertEqual(len(glasses.content_hash), 64)
        with self.assertRaises(UserError):
            glasses.sph_od = -3
        no_license = self.env['oph.glasses.prescription'].create({'patient_id': self.patient.id, 'doctor_id': self.reception.id,
                                                                 'sph_od': -1})
        with self.assertRaises(UserError):
            no_license.action_issue()

    def test_prescription(self):
        drop = self.ref('product_med_med002')
        prescription = self.env['oph.prescription'].create({
            'patient_id': self.patient.id, 'doctor_id': self.doctor.id,
            'line_ids': [(0, 0, {'product_id': drop.id, 'eye': 'ou'})]})
        self.assertEqual(prescription.insurance_id, self.insurance)
        self.assertEqual(prescription.line_ids.active_ingredient, drop.oph_active_ingredient)
        with self.assertRaises(UserError):
            prescription.action_issue()  # diagnosis missing
        prescription.diagnosis_id = self.glaucoma
        prescription.action_issue()
        prescription.write({'cuir': '0001-0002-03-0004-ABC-05'})  # registered platform code can be added later
        with self.assertRaises(UserError):
            prescription.notes = "cambio"

    def test_consent_sign_lock_and_minor(self):
        template = self.ref('consent_template_cataract')
        consent = self.env['oph.consent'].create({'patient_id': self.patient.id, 'template_id': template.id,
                                                 'procedure': "Facoemulsificación OD", 'doctor_id': self.doctor.id})
        self.assertIn("Paciente Test", str(consent.content))
        self.assertIn("Facoemulsificación OD", str(consent.content))
        self.assertNotIn('{patient}', str(consent.content))
        consent._sign("Paciente Test", SIGNATURE, ip='127.0.0.1')
        self.assertEqual(consent.state, 'signed')
        self.assertEqual(consent.signature_hash, consent._get_signature_hash())
        with self.assertRaises(UserError):
            consent.content = "<p>otro</p>"
        with self.assertRaises(UserError):
            consent.unlink()
        child = self.env['res.partner'].create({'name': "Niño Test", 'is_oph_patient': True,
                                                'oph_birthdate': fields.Date.today() - timedelta(days=365 * 8)})
        minor = self.env['oph.consent'].create({'patient_id': child.id, 'template_id': template.id})
        self.assertEqual(minor.signer_role, 'guardian')

    def test_certificate(self):
        exam = self._exam(va_cc_od='1.0', va_cc_os='0.9')
        certificate = self.env['oph.certificate'].create({'patient_id': self.patient.id, 'exam_id': exam.id,
                                                         'doctor_id': self.doctor.id, 'certificate_type': 'visual_fitness'})
        self.assertIn('1.0', str(certificate.body))
        self.assertIn('Paciente Test', str(certificate.body))
        certificate.action_issue()
        with self.assertRaises(UserError):
            certificate.body = "<p>x</p>"


class TestSurgery(OphCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.iol = cls.ref('product_iol_lio_mono_hfob')
        cls.lot = cls.env['stock.lot'].create({'name': 'SN-TEST-001', 'product_id': cls.iol.id,
                                               'expiration_date': fields.Datetime.now() + timedelta(days=700)})
        location = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1).lot_stock_id
        cls.env['stock.quant']._update_available_quantity(cls.iol, location, 1, lot_id=cls.lot)
        cls.room = cls.ref('room_operating')
        cls.procedure = cls.ref('procedure_faco_mono')
        cls.env['oph.insurance.price'].create({
            'insurance_id': cls.insurance.id, 'product_id': cls.procedure.product_id.product_tmpl_id.id,
            'insurance_amount': 1000000, 'requires_authorization': True,
        })

    def _surgery(self, start=None, **vals):
        values = {'patient_id': self.patient.id, 'procedure_id': self.procedure.id, 'eye': 'od',
                  'surgeon_id': self.doctor.id, 'room_id': self.room.id,
                  'start': start or fields.Datetime.now() + timedelta(days=2)}
        values.update(vals)
        return self.env['oph.surgery'].create(values)

    def test_overlap_and_event(self):
        surgery = self._surgery()
        self.assertTrue(surgery.event_id)
        self.assertEqual(surgery.event_id.user_id, self.doctor)
        self.assertEqual(surgery.line_ids.product_id, self.procedure.product_id)
        with self.assertRaises(ValidationError):
            self._surgery(start=surgery.start + timedelta(minutes=10))

    def test_full_surgery_flow(self):
        surgery = self._surgery()
        with self.assertRaises(UserError):
            surgery.action_confirm()  # waiting authorization (insurer price needs it)
        surgery.authorization = 'AUT-1'
        surgery.action_authorize()
        surgery.action_confirm()
        self.assertEqual(surgery.state, 'confirmed')
        with self.assertRaises(UserError):
            surgery.action_start()  # consent missing
        consent = self.env['oph.consent'].browse(surgery.action_prepare_consent()['res_id'])
        self.assertEqual(consent.template_id, self.procedure.consent_template_id)
        consent._sign("Paciente Test", SIGNATURE)
        self.assertTrue(surgery.consent_ok)
        with self.assertRaises(UserError):
            surgery.action_start()  # lens missing
        surgery.write({'iol_product_id': self.iol.id, 'iol_lot_id': self.lot.id, 'iol_power': 21.5})
        with self.assertRaises(UserError):
            surgery.action_start()  # checklist
        surgery.write({name: True for name in ('check_identity', 'check_site_marked', 'check_fasting',
                                               'check_anticoagulants', 'check_allergies', 'check_preop_assessment',
                                               'check_timeout', 'check_iol_verified')})
        surgery.action_start()
        with self.assertRaises(UserError):
            surgery.action_done()  # protocol
        surgery.write({'protocol': "<p>Sin complicaciones.</p>", 'check_count_sign_out': True})
        surgery.action_done()
        self.assertEqual(surgery.state, 'done')
        self.assertEqual(len(surgery.postop_event_ids), 3)
        lens_line = surgery.line_ids.filtered(lambda l: l.product_id == self.iol)
        self.assertEqual(lens_line.lot_id, self.lot)
        self.assertEqual(surgery.claim_ids.authorization, 'AUT-1')
        order = surgery.sale_order_ids
        self.assertTrue(order)
        order.action_confirm()
        move_line = order.picking_ids.move_ids.filtered(lambda m: m.product_id == self.iol).move_line_ids
        self.assertEqual(move_line.lot_id, self.lot)

    def test_expired_lens_rejected(self):
        expired = self.env['stock.lot'].create({'name': 'SN-OLD', 'product_id': self.iol.id,
                                                'expiration_date': fields.Datetime.now() - timedelta(days=1)})
        with self.assertRaises(ValidationError):
            self._surgery(iol_product_id=self.iol.id, iol_lot_id=expired.id)

    def test_iol_requires_tracking(self):
        with self.assertRaises(ValidationError):
            self.env['product.template'].create({'name': "Lente sin serie", 'type': 'consu', 'is_storable': True,
                                                 'tracking': 'none', 'oph_kind': 'iol'})


class TestBillingAndReminders(OphCommon):

    def test_settlement_and_price_update(self):
        for _i in range(2):
            exam = self._exam(line_ids=[(0, 0, {'product_id': self.consult.id})])
            exam.action_start()
            exam.action_done()
        settlement = self.env['oph.insurance.settlement'].create({
            'insurance_id': self.insurance.id, 'date_from': fields.Date.today() - timedelta(days=31),
            'date_to': fields.Date.today()})
        settlement.action_load_claims()
        self.assertEqual(settlement.claim_count, 2)
        self.assertEqual(settlement.amount_total, 60000)
        action = settlement.action_export_csv()
        self.assertIn('/web/content/', action['url'])
        settlement.action_create_invoice()
        self.assertEqual(settlement.state, 'invoiced')
        self.assertEqual(settlement.invoice_id.partner_id, self.insurance.partner_id)
        self.assertEqual(settlement.invoice_id.amount_total, 60000)
        self.assertTrue(all(c.state == 'billed' for c in settlement.claim_ids))
        wizard = self.env['oph.price.update'].create({'insurance_ids': [(6, 0, self.insurance.ids)], 'percentage': 10,
                                                      'rounding': 100})
        wizard.action_apply()
        self.assertEqual(self.insurance.price_ids.insurance_amount, 33000)
        self.assertEqual(self.insurance.price_ids.copay_amount, 5500)

    def test_claim_rejection_and_rebill(self):
        exam = self._exam(line_ids=[(0, 0, {'product_id': self.consult.id})])
        exam.action_start()
        exam.action_done()
        claim = exam.claim_ids
        with self.assertRaises(UserError):
            claim.action_reject()
        claim.rejection_reason = "Afiliado sin cobertura"
        claim.action_reject()
        claim.action_rebill()
        self.assertEqual(claim.state, 'to_bill')

    def test_reminders(self):
        exam = self._exam()
        exam.action_start()
        exam.action_done()
        exam.with_context(oph_allow_closed_edit=True).next_control_date = fields.Date.today() + timedelta(days=5)
        self.env['res.partner']._cron_oph_control_recall()
        self.assertEqual(self.patient.oph_recall_sent_for, exam.next_control_date)
        tomorrow = fields.Datetime.now() + timedelta(days=1)
        event = self.env['calendar.event'].create({'oph_patient_id': self.patient.id, 'start': tomorrow,
                                                   'stop': tomorrow + timedelta(minutes=20), 'user_id': self.doctor.id})
        self.env['calendar.event']._cron_oph_appointment_reminders()
        self.assertTrue(event.oph_reminder_sent or not (fields.Datetime.context_timestamp(event, tomorrow).date()
                                                        == fields.Date.context_today(event) + timedelta(days=1)))
        self.assertIn(self.patient.name.split(' ')[0], event._oph_reminder_message())


class TestDemoAndReports(OphCommon):

    def test_demo_and_reports(self):
        if not self.env['ir.config_parameter'].sudo().get_param('odossey_ophthalmology.demo_loaded'):
            self.env['oph.demo'].load_demo()
        with self.assertRaises(UserError):
            self.env['oph.demo'].load_demo()
        self.assertTrue(self.env['oph.surgery'].search([('state', '=', 'done')]))
        self.assertTrue(self.env['oph.insurance.settlement'].search([]).claim_ids)
        for xmlid, model, domain in (
                ('action_report_exam', 'oph.exam', [('state', '=', 'done')]),
                ('action_report_glasses', 'oph.glasses.prescription', [('state', '=', 'issued')]),
                ('action_report_prescription', 'oph.prescription', [('state', '=', 'issued')]),
                ('action_report_study', 'oph.study', [('state', '=', 'reported')]),
                ('action_report_surgery', 'oph.surgery', [('state', '=', 'done')]),
                ('action_report_implant_card', 'oph.surgery', [('state', '=', 'done')]),
                ('action_report_consent', 'oph.consent', [('state', '=', 'signed')]),
                ('action_report_certificate', 'oph.certificate', [('state', '=', 'issued')]),
                ('action_report_settlement', 'oph.insurance.settlement', []),
                ('action_report_clinical_record', 'res.partner', [('oph_exam_ids', '!=', False)])):
            record = self.env[model].search(domain, limit=1)
            self.assertTrue(record, xmlid)
            html, _type = self.env['ir.actions.report']._render_qweb_html(
                'odossey_ophthalmology.%s' % xmlid, record.ids)
            self.assertTrue(html, xmlid)


@tagged('post_install', '-at_install')
class TestPortalAndUi(HttpCase):

    def test_actions_context_is_literal(self):
        data = self.env['ir.model.data'].search([('module', '=', 'odossey_ophthalmology'),
                                                 ('model', '=', 'ir.actions.act_window')])
        for action in self.env['ir.actions.act_window'].browse(data.mapped('res_id')):
            self.assertNotIn('ref(', action.context or '', action.name)

    def test_menus_open(self):
        menus = self.env['ir.ui.menu'].search([('id', 'child_of', self.env.ref('odossey_ophthalmology.menu_oph_root').id),
                                               ('action', '!=', False)])
        for menu in menus:
            action = menu.action
            if action._name != 'ir.actions.act_window':
                continue
            model = self.env[action.res_model]
            domain = action.domain and eval(action.domain, {'uid': self.env.uid}) or []  # noqa: S307
            model.search(domain, limit=1)
            for view_mode in action.view_mode.split(','):
                if view_mode in ('list', 'form', 'kanban', 'calendar', 'pivot', 'graph', 'activity'):
                    model.get_views([(False, view_mode)])

    def test_portal_patient_sees_own_documents(self):
        env = self.env(context=dict(self.env.context, tracking_disable=True))
        doctor = env['res.users'].with_context(no_reset_password=True).create({
            'name': "Dr. Portal", 'login': 'oph.portal.doctor', 'oph_is_ophthalmologist': True, 'oph_license': 'MN 1',
            'group_ids': [(4, env.ref('odossey_ophthalmology.group_oph_ophthalmologist').id)]})
        patient_user = env['res.users'].with_context(no_reset_password=True).create({
            'name': "Paciente Portal", 'login': 'oph.portal.patient', 'password': 'oph.portal.patient',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        patient = patient_user.partner_id
        patient.is_oph_patient = True
        other = env['res.partner'].create({'name': "Otro Paciente", 'is_oph_patient': True})
        mine = env['oph.glasses.prescription'].create({'patient_id': patient.id, 'doctor_id': doctor.id, 'sph_od': -1})
        theirs = env['oph.glasses.prescription'].create({'patient_id': other.id, 'doctor_id': doctor.id, 'sph_od': -2})
        (mine | theirs).action_issue()
        self.authenticate('oph.portal.patient', 'oph.portal.patient')
        response = self.url_open('/my/ophthalmology')
        self.assertEqual(response.status_code, 200)
        self.assertIn(mine.name, response.text)
        self.assertNotIn(theirs.name, response.text)
        response = self.url_open('/my/ophthalmology/glasses/%s' % mine.id)
        self.assertEqual(response.headers.get('Content-Type'), 'application/pdf')
        response = self.url_open('/my/ophthalmology/glasses/%s' % theirs.id)
        self.assertNotEqual(response.headers.get('Content-Type'), 'application/pdf')
