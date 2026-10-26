import base64
from datetime import datetime, time, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# 1x1 transparent PNG, used as the handwritten signature of the demo consents
DEMO_SIGNATURE = base64.b64encode(base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='))


class OphDemo(models.AbstractModel):
    _name = 'oph.demo'
    _description = 'Ophthalmology Demo Data'

    def _ref(self, xmlid):
        return self.env.ref('odossey_ophthalmology.%s' % xmlid)

    def _local(self, day, hour, minute=0):
        """Datetime (UTC, naive) for a local hour of the clinic."""
        tz = pytz.timezone(self.env.user.tz or 'America/Argentina/Buenos_Aires')
        return tz.localize(datetime.combine(day, time(hour, minute))).astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def load_demo(self):
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Only administrators can load the demo data."))
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('odossey_ophthalmology.demo_loaded'):
            raise UserError(_("The demo data is already loaded."))
        if not self.env.user.tz:
            self.env.user.tz = 'America/Argentina/Buenos_Aires'
        today = fields.Date.context_today(self)
        ar = self.env.ref('base.ar')
        langs = [code for code, _name in self.env['res.lang'].get_installed()]
        patient_lang = next((code for code in ('es_AR', 'es_419', 'es_ES') if code in langs), self.env.lang)

        # ------------------------------------------------------------ professionals
        Users = self.env['res.users'].with_context(no_reset_password=True)
        doctor_group = self._ref('group_oph_ophthalmologist')
        tech_group = self._ref('group_oph_technician')
        reception_group = self._ref('group_oph_reception')

        def user(name, login, group, **vals):
            record = Users.search([('login', '=', login)], limit=1) or Users.create({
                'name': name, 'login': login, 'email': login, 'group_ids': [(4, group.id)],
                'tz': self.env.user.tz, 'lang': patient_lang,
            })
            record.write(vals)
            return record

        sosa = user("Dra. Valeria Sosa", 'valeria.sosa@clinicavision.com.ar', doctor_group, oph_is_ophthalmologist=True,
                    oph_license='98.231', oph_license_provincial='44.120', oph_specialty="Oftalmología - Glaucoma")
        iriarte = user("Dr. Martín Iriarte", 'martin.iriarte@clinicavision.com.ar', doctor_group, oph_is_ophthalmologist=True,
                       oph_license='87.554', oph_specialty="Oftalmología - Cirugía de catarata y retina")
        benitez = user("Lic. Paula Benítez", 'paula.benitez@clinicavision.com.ar', tech_group, oph_is_technician=True,
                       oph_specialty="Ortóptica")
        user("Carla Domínguez", 'recepcion@clinicavision.com.ar', reception_group)
        admin = self.env.user
        if not admin.oph_license:
            admin.write({'oph_is_ophthalmologist': True, 'oph_license': '75.002'})

        # ------------------------------------------------------------ insurers, plans and agreed fees
        osde = self._ref('insurance_osde')
        pami = self._ref('insurance_pami')
        swiss = self._ref('insurance_swiss')
        galeno = self._ref('insurance_galeno')
        for insurance, plans in ((osde, ['210', '310', '410']), (swiss, ['SMG20', 'SMG30']), (galeno, ['Plata', 'Oro']),
                                 (pami, ['Jubilados'])):
            for plan in plans:
                if plan not in insurance.plan_ids.mapped('name'):
                    insurance.plan_ids = [(0, 0, {'name': plan})]
        fees = {  # product xmlid: (nomenclator code, insurer amount, co-payment, authorization)
            'product_cons_1v': ('420101', 32000, 6000, False),
            'product_cons_ctrl': ('420101', 26000, 6000, False),
            'product_oct_mac': ('305111', 48000, 9000, True),
            'product_oct_no': ('305111', 48000, 9000, True),
            'product_cv': ('300102', 36000, 7000, False),
            'product_biom_opt': ('300105', 42000, 8000, True),
            'product_proc_faco_mono': ('306075', 1450000, 0, True),
            'product_proc_ivt': ('306102', 180000, 0, True),
        }
        for insurance, factor in ((osde, 1.15), (swiss, 1.1), (galeno, 1.0), (pami, 0.8)):
            insurance.partner_id.write({'country_id': ar.id, 'is_company': True})
            for xmlid, (code, amount, copay, auth) in fees.items():
                template = self._ref(xmlid).product_tmpl_id
                if not insurance.price_ids.filtered(lambda p: p.product_id == template):
                    insurance.price_ids = [(0, 0, {
                        'product_id': template.id, 'nomenclator_code': code, 'insurance_amount': round(amount * factor, -2),
                        'copay_amount': 0 if insurance == pami else copay, 'requires_authorization': auth,
                    })]

        # ------------------------------------------------------------ patients
        Partner = self.env['res.partner'].with_context(tracking_disable=True)
        allergy = self._ref

        def patient(name, document, birth, gender, phone, email, street, city, insurance=None, plan=None, member=None, **vals):
            values = {
                'name': name, 'is_oph_patient': True, 'oph_document': document, 'oph_birthdate': birth,
                'oph_gender': gender, 'phone': phone, 'email': email, 'street': street, 'city': city,
                'country_id': ar.id, 'lang': patient_lang,
                'oph_insurance_id': insurance.id if insurance else False,
                'oph_plan_id': insurance.plan_ids.filtered(lambda p: p.name == plan)[:1].id if insurance and plan else False,
                'oph_member_number': member,
            }
            values.update(vals)
            return Partner.create(values)

        gomez = patient("Roberto Gómez", '12.345.678', '1951-03-14', 'male', '+54 9 11 4567-1234', 'roberto.gomez@example.com',
                        "Av. Rivadavia 4520", "Buenos Aires", pami, 'Jubilados', '150123456789-00',
                        oph_hypertension=True, oph_glaucoma_family=True,
                        oph_medical_history="Hipertensión arterial en tratamiento con enalapril.",
                        oph_ocular_history="Glaucoma primario de ángulo abierto diagnosticado en 2021.")
        fernandez = patient("Marta Fernández", '14.987.321', '1956-07-02', 'female', '+54 9 11 5523-8890', 'marta.fernandez@example.com',
                            "Thames 1820", "Buenos Aires", osde, '310', '61234567-01',
                            oph_tamsulosin=False, oph_anticoagulated=True,
                            oph_allergy_ids=[(4, allergy('allergy_penicillin').id)],
                            oph_medical_history="Fibrilación auricular, anticoagulada con apixabán.",
                            oph_ocular_history="Usa anteojos para cerca desde los 45 años.")
        ruiz = patient("Jorge Ruiz", '20.456.789', '1968-11-23', 'male', '+54 9 11 3344-5566', 'jorge.ruiz@example.com',
                       "Av. Cabildo 2230", "Buenos Aires", swiss, 'SMG30', '0099-123456-02', oph_diabetes=True,
                       oph_medical_history="Diabetes tipo 2 desde 2012, metformina e insulina.")
        lopez = patient("Ana López", '33.222.111', '1988-05-09', 'female', '+54 9 11 6677-1122', 'ana.lopez@example.com',
                        "Gurruchaga 950", "Buenos Aires", osde, '210', '61987654-01', oph_contact_lens_user=True,
                        oph_ocular_history="Miopía desde la adolescencia, usa lentes de contacto mensuales.")
        torres = patient("Lucas Torres", '52.111.333', '2016-08-30', 'male', '+54 9 11 2233-4455', 'familia.torres@example.com',
                         "Ciudad de la Paz 1450", "Buenos Aires", galeno, 'Plata', '7788990-03',
                         oph_referred_by="Pediatra - Dr. Acosta")
        medina = patient("Silvia Medina", '17.654.987', '1963-01-18', 'female', '+54 9 11 4455-6677', 'silvia.medina@example.com',
                         "Av. Corrientes 3100", "Buenos Aires", oph_allergy_ids=[(4, allergy('allergy_benzalkonium').id)])
        castro = patient("Héctor Castro", '10.222.444', '1947-09-05', 'male', '+54 9 11 7788-9900', 'hector.castro@example.com',
                         "Av. San Martín 5600", "Buenos Aires", pami, 'Jubilados', '150987654321-00',
                         oph_diabetes=True, oph_hypertension=True,
                         oph_ocular_history="Degeneración macular asociada a la edad, tratada con antiangiogénicos.")
        vega = patient("Paula Vega", '38.765.432', '1994-12-12', 'female', '+54 9 11 9988-7766', 'paula.vega@example.com',
                       "Honduras 4100", "Buenos Aires", osde, '410', '61555444-02')
        patients = gomez | fernandez | ruiz | lopez | torres | medina | castro | vega

        # ------------------------------------------------------------ lens stock with serial numbers
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        location = warehouse.lot_stock_id
        iol = self._ref('product_iol_lio_mono_hfob')
        toric = self._ref('product_iol_lio_torica')
        Lot = self.env['stock.lot']
        serials = {}
        for product, prefix, count in ((iol, 'SN60WF', 6), (toric, 'TFNT', 2)):
            for index in range(count):
                lot = Lot.create({'name': '%s-%s%03d' % (prefix, today.strftime('%y'), 101 + index), 'product_id': product.id,
                                  'expiration_date': fields.Datetime.now() + relativedelta(years=3)})
                self.env['stock.quant']._update_available_quantity(product, location, 1, lot_id=lot)
                serials.setdefault(product, []).append(lot)
        for xmlid, qty in (('product_sup_visco_disp', 10), ('product_sup_pack_faco', 8), ('product_sup_kit_ivt', 12)):
            product = self._ref(xmlid)
            lot = Lot.create({'name': 'L%s-%s' % (today.strftime('%y%m'), product.default_code), 'product_id': product.id,
                              'expiration_date': fields.Datetime.now() + relativedelta(years=1)})
            self.env['stock.quant']._update_available_quantity(product, location, qty, lot_id=lot)

        # ------------------------------------------------------------ past exams (closed)
        Exam = self.env['oph.exam'].with_context(tracking_disable=True, oph_allow_closed_edit=True)
        diag = self._ref

        def exam(patient_rec, doctor, when, diagnoses, technician=None, close=True, **vals):
            values = {'patient_id': patient_rec.id, 'doctor_id': doctor.id, 'date': when,
                      'technician_id': (technician or benitez).id, 'iop_method': 'goldmann',
                      'diagnosis_ids': [(0, 0, {'diagnosis_id': diag(d).id, 'eye': eye}) for d, eye in diagnoses]}
            values.update(vals)
            record = Exam.create(values)
            if close:
                record.line_ids = [(0, 0, {'product_id': self._ref('product_cons_ctrl').id, 'quantity': 1})]
                record.with_user(doctor).action_start()
                record.with_user(doctor).action_done()
            return record

        normal_segment = {'lids_od': "Normales", 'lids_os': "Normales", 'conjunctiva_od': "Clara", 'conjunctiva_os': "Clara",
                          'cornea_od': "Transparente", 'cornea_os': "Transparente",
                          'anterior_chamber_od': "Formada, Van Herick 4", 'anterior_chamber_os': "Formada, Van Herick 4",
                          'pupils': "Isocóricas, reactivas, sin DPAR", 'motility': "Conservada, ortoforia"}
        # glaucoma follow-up of Roberto Gómez: pressure goes down after treatment
        for months, iop_od, iop_os, plan in ((14, 26.0, 24.0, "Se inicia latanoprost 1 gota por la noche en ambos ojos."),
                                             (10, 19.0, 18.0, "Buena respuesta al tratamiento. Continuar."),
                                             (6, 17.0, 16.0, "PIO en objetivo. Campo visual estable."),
                                             (2, 18.0, 17.0, "Estable. Control en 4 meses con campo visual y OCT de nervio óptico.")):
            exam(gomez, sosa, self._local(today - relativedelta(months=months), 10), [('diagnosis_h40_1', 'ou')],
                 visit_type='control', reason="Control de glaucoma", va_cc_od='0.8', va_cc_os='0.9',
                 iop_od=iop_od, iop_os=iop_os, cup_disc_od=0.7, cup_disc_os=0.6, pachymetry_od=545, pachymetry_os=550,
                 rx_sph_od=1.0, rx_cyl_od=-0.5, rx_axis_od=90, rx_add_od=2.5, rx_sph_os=1.25, rx_cyl_os=-0.75,
                 rx_axis_os=85, rx_add_os=2.5, rx_va_od='0.9', rx_va_os='1.0', lens_grade_od='1', lens_grade_os='1',
                 disc_od="Excavación vertical, borde neural adelgazado inferior", disc_os="Excavación aumentada",
                 macula_od="Normal", macula_os="Normal", plan="<p>%s</p>" % plan, **normal_segment)
        # cataract of Marta Fernández → surgery
        cataract_exam = exam(fernandez, iriarte, self._local(today - timedelta(days=40), 11),
                             [('diagnosis_h25_1', 'od'), ('diagnosis_h52_4', 'ou')], visit_type='first',
                             reason="Disminución de la visión del ojo derecho", va_sc_od='0.3', va_sc_os='0.7',
                             va_cc_od='0.4', va_cc_os='0.9', iop_od=15.0, iop_os=16.0, lens_grade_od='3', lens_grade_os='1',
                             rx_sph_od=-2.0, rx_cyl_od=-1.0, rx_axis_od=180, rx_add_od=2.75, rx_va_od='0.4',
                             rx_sph_os=0.5, rx_cyl_os=-0.5, rx_axis_os=175, rx_add_os=2.75, rx_va_os='0.9',
                             cup_disc_od=0.3, cup_disc_os=0.3, macula_od="Normal", macula_os="Normal",
                             plan="<p>Catarata nuclear OD que limita la visión. Se indica facoemulsificación con LIO "
                                  "monofocal en ojo derecho. Se solicita biometría óptica.</p>", **normal_segment)
        # diabetic retinopathy of Jorge Ruiz
        exam(ruiz, iriarte, self._local(today - timedelta(days=20), 9, 30), [('diagnosis_h36_0', 'ou'), ('diagnosis_h35_8', 'od')],
             visit_type='control', reason="Control de retinopatía diabética", va_cc_od='0.6', va_cc_os='0.9',
             iop_od=16.0, iop_os=15.0, dilated=True, cup_disc_od=0.3, cup_disc_os=0.3,
             macula_od="Edema macular con exudados duros", macula_os="Sin edema",
             vessels_od="Microaneurismas y hemorragias en 4 cuadrantes", vessels_os="Microaneurismas aislados",
             plan="<p>Edema macular diabético OD. Se indican inyecciones intravítreas de aflibercept. OCT macular de control.</p>",
             **normal_segment)
        # myopia and contact lenses of Ana López
        lopez_exam = exam(lopez, sosa, self._local(today - timedelta(days=12), 17), [('diagnosis_h52_1', 'ou'), ('diagnosis_h52_2', 'ou')],
                          visit_type='contact_lens', reason="Renovación de receta de anteojos y lentes de contacto",
                          va_sc_od='0.1', va_sc_os='0.1', va_cc_od='1.0', va_cc_os='1.0', iop_od=14.0, iop_os=14.0,
                          rx_sph_od=-4.25, rx_cyl_od=-0.75, rx_axis_od=10, rx_sph_os=-4.0, rx_cyl_os=-0.5, rx_axis_os=170,
                          rx_va_od='1.0', rx_va_os='1.0', pd_distance=62.0, k1_od=43.25, k2_od=44.0, k1_os=43.5, k2_os=44.0,
                          cup_disc_od=0.3, cup_disc_os=0.3, **normal_segment)
        # macular degeneration of Héctor Castro
        exam(castro, iriarte, self._local(today - timedelta(days=30), 10, 30), [('diagnosis_h35_3', 'os')],
             visit_type='control', reason="Control DMAE", va_cc_od='0.7', va_cc_os='0.2', iop_od=17.0, iop_os=18.0,
             dilated=True, macula_od="Drusas duras", macula_os="Membrana neovascular con líquido subretinal",
             lens_grade_od='pseudophakic', lens_grade_os='2',
             plan="<p>DMAE neovascular OI activa. Continuar inyecciones intravítreas.</p>", **normal_segment)

        # ------------------------------------------------------------ studies
        Study = self.env['oph.study'].with_context(tracking_disable=True)
        biometry = Study.create({'patient_id': fernandez.id, 'exam_id': cataract_exam.id, 'eye': 'od',
                                 'study_type_id': self._ref('study_type_biom_opt').id, 'technician_id': benitez.id,
                                 'date': self._local(today - timedelta(days=35), 9), 'axial_length_od': 23.45,
                                 'acd_od': 3.1, 'iol_power_od': 21.5, 'iol_formula': 'barrett', 'target_refraction': -0.25,
                                 'conclusion': "LIO monofocal +21,5 D para emetropía OD (Barrett)."})
        biometry.with_user(iriarte).action_report()
        oct_ruiz = Study.create({'patient_id': ruiz.id, 'eye': 'ou', 'study_type_id': self._ref('study_type_oct_mac').id,
                                 'technician_id': benitez.id, 'date': self._local(today - timedelta(days=19), 9),
                                 'cmt_od': 412, 'cmt_os': 268, 'result_od': "Edema macular quístico",
                                 'result_os': "Perfil foveal conservado",
                                 'conclusion': "Edema macular diabético OD."})
        oct_ruiz.with_user(iriarte).action_report()
        cv_gomez = Study.create({'patient_id': gomez.id, 'eye': 'ou', 'study_type_id': self._ref('study_type_cv').id,
                                 'technician_id': benitez.id, 'date': self._local(today - relativedelta(months=2), 9),
                                 'md_od': -4.2, 'md_os': -2.1, 'psd_od': 5.3, 'psd_os': 2.8, 'vfi_od': 89, 'vfi_os': 96,
                                 'conclusion': "Escalón nasal superior OD. OI dentro de límites normales."})
        cv_gomez.with_user(sosa).action_report()
        Study.create({'patient_id': gomez.id, 'eye': 'ou', 'study_type_id': self._ref('study_type_oct_no').id})
        Study.create({'patient_id': castro.id, 'eye': 'os', 'study_type_id': self._ref('study_type_oct_mac').id,
                      'state': 'scheduled'})

        # ------------------------------------------------------------ documents
        glasses = self.env['oph.glasses.prescription'].create({
            'patient_id': lopez.id, 'exam_id': lopez_exam.id, 'doctor_id': sosa.id, 'lens_use': 'distance',
            'sph_od': -4.25, 'cyl_od': -0.75, 'axis_od': 10, 'sph_os': -4.0, 'cyl_os': -0.5, 'axis_os': 170,
            'pd_distance': 62.0, 'lens_recommendations': "Antirreflejo",
        })
        glasses.action_issue()
        contact = self.env['oph.glasses.prescription'].create({
            'patient_id': lopez.id, 'exam_id': lopez_exam.id, 'doctor_id': sosa.id, 'prescription_type': 'contact_lens',
            'sph_od': -4.0, 'sph_os': -3.75, 'cl_base_curve_od': 8.6, 'cl_base_curve_os': 8.6, 'cl_diameter_od': 14.2,
            'cl_diameter_os': 14.2, 'cl_brand': "Lente blanda de silicona hidrogel", 'cl_replacement': 'monthly',
        })
        contact.action_issue()
        prescription = self.env['oph.prescription'].create({
            'patient_id': gomez.id, 'doctor_id': sosa.id, 'diagnosis_id': self._ref('diagnosis_h40_1').id,
            'line_ids': [(0, 0, {'product_id': self._ref('product_med_med002').id, 'eye': 'ou', 'duration': "Crónico",
                                 'quantity': 2})],
            'notes': "Aplicar a la noche. Cerrar los ojos 1 minuto después de cada gota.",
        })
        prescription.action_issue()
        prescription.write({'cuir': '0123-4567-89-0001-2026A1B2C3-07', 'platform': "Plataforma de receta electrónica"})
        certificate = self.env['oph.certificate'].create({
            'patient_id': vega.id, 'doctor_id': sosa.id, 'certificate_type': 'visual_fitness',
        })
        certificate.action_issue()

        # ------------------------------------------------------------ surgeries
        Surgery = self.env['oph.surgery'].with_context(tracking_disable=True)
        operating = self._ref('room_operating')
        lens_lot = serials[iol][0]
        # done 3 weeks ago (another patient) with lens traceability
        done = Surgery.create({
            'patient_id': castro.id, 'procedure_id': self._ref('procedure_faco_mono').id, 'eye': 'od',
            'surgeon_id': iriarte.id, 'room_id': operating.id, 'anesthetist': "Dr. Pablo Quiroga",
            'start': self._local(today - timedelta(days=21), 8), 'authorization': 'PAMI-OME-552310',
            'iol_product_id': iol.id, 'iol_lot_id': serials[iol][5].id, 'iol_power': 22.0, 'iol_formula': 'barrett',
        })
        done.action_authorize()
        done.action_confirm()
        consent = self.env['oph.consent'].search([('surgery_id', '=', done.id)], limit=1) or \
            self.env['oph.consent'].browse(done.action_prepare_consent()['res_id'])
        consent._sign(castro.name, DEMO_SIGNATURE, ip='127.0.0.1')
        done.write({name: True for name in ('check_identity', 'check_site_marked', 'check_fasting', 'check_anticoagulants',
                                            'check_allergies', 'check_preop_assessment', 'check_timeout',
                                            'check_iol_verified')})
        done.with_user(iriarte).action_start()
        done.write({'protocol': "<p>Anestesia tópica más sedación. Incisión principal temporal de 2,2 mm, capsulorrexis "
                                "circular continua, facoemulsificación en técnica stop and chop, aspiración de corteza e "
                                "implante de LIO en saco capsular. Sin complicaciones.</p>",
                    'postop_instructions': "Moxifloxacina + dexametasona 1 gota cada 6 horas. Usar protector nocturno. "
                                           "Consultar ante dolor o baja de visión.",
                    'check_count_sign_out': True,
                    'line_ids': [(0, 0, {'product_id': self._ref('product_sup_pack_faco').id, 'quantity': 1, 'billing': 'free'}),
                                 (0, 0, {'product_id': self._ref('product_sup_visco_disp').id, 'quantity': 1, 'billing': 'free'})]})
        done.with_user(iriarte).action_done()
        done.actual_start = self._local(today - timedelta(days=21), 8, 5)
        done.actual_end = self._local(today - timedelta(days=21), 8, 32)
        # planned next week: Marta Fernández right eye
        planned = Surgery.create({
            'patient_id': fernandez.id, 'exam_id': cataract_exam.id, 'procedure_id': self._ref('procedure_faco_mono').id,
            'eye': 'od', 'surgeon_id': iriarte.id, 'room_id': operating.id, 'biometry_id': biometry.id,
            'start': self._local(today + timedelta(days=7), 8), 'iol_product_id': iol.id, 'iol_lot_id': lens_lot.id,
            'iol_power': 21.5, 'iol_formula': 'barrett', 'target_refraction': -0.25,
        })
        planned.action_prepare_consent()
        # intravitreal injection for Jorge Ruiz, waiting for the authorization
        Surgery.create({
            'patient_id': ruiz.id, 'procedure_id': self._ref('procedure_ivt').id, 'eye': 'od', 'surgeon_id': iriarte.id,
            'room_id': self._ref('room_laser').id, 'start': self._local(today + timedelta(days=3), 13),
        })

        # ------------------------------------------------------------ agenda: today, tomorrow and next days
        Event = self.env['calendar.event'].with_context(tracking_disable=True, no_mail_to_attendees=True)
        first = self._ref('appointment_type_primera_vez')
        control = self._ref('appointment_type_control')
        glaucoma_control = self._ref('appointment_type_control_glaucoma')
        study_type = self._ref('appointment_type_estudios')
        pediatric = self._ref('appointment_type_pediatria')
        room1 = self._ref('room_consulting_1')
        room2 = self._ref('room_consulting_2')
        agenda = [
            (0, 8, 30, gomez, glaucoma_control, sosa, room1, 'done', "Control de glaucoma"),
            (0, 9, 0, vega, first, sosa, room1, 'in_consultation', "Certificado para licencia de conducir"),
            (0, 9, 30, medina, first, sosa, room1, 'dilating', "Visión borrosa de cerca"),
            (0, 10, 0, torres, pediatric, sosa, room2, 'arrived', "Control escolar, entrecierra los ojos"),
            (0, 10, 30, ruiz, study_type, iriarte, self._ref('room_studies'), 'pre_consultation', "OCT macular de control"),
            (0, 11, 0, lopez, control, sosa, room1, 'confirmed', "Control de lentes de contacto"),
            (0, 12, 0, castro, control, iriarte, room2, 'booked', "Control DMAE"),
            (1, 9, 0, fernandez, control, iriarte, room2, 'confirmed', "Evaluación prequirúrgica"),
            (1, 10, 0, medina, control, sosa, room1, 'booked', "Resultado de estudios"),
            (2, 16, 0, vega, control, sosa, room1, 'booked', "Control"),
        ]
        now = fields.Datetime.now()
        for days, hour, minute, patient_rec, atype, doctor, room, state, reason in agenda:
            start = self._local(today + timedelta(days=days), hour, minute)
            vals = {'oph_patient_id': patient_rec.id, 'oph_appointment_type_id': atype.id, 'user_id': doctor.id,
                    'oph_room_id': room.id, 'start': start, 'stop': start + timedelta(minutes=atype.duration),
                    'oph_reason': reason, 'oph_state': 'booked'}
            event = Event.create(vals)
            if state in ('arrived', 'pre_consultation', 'dilating', 'in_consultation', 'done'):
                event.oph_arrival_time = now - timedelta(minutes={'arrived': 12, 'pre_consultation': 25, 'dilating': 40,
                                                                  'in_consultation': 55, 'done': 90}[state])
            if state == 'pre_consultation':
                event.with_user(benitez).action_oph_start_pre_consultation()
            elif state == 'in_consultation':
                exam_rec = event._oph_get_or_create_exam()
                exam_rec.write({'technician_id': benitez.id, 'va_sc_od': '1.0', 'va_sc_os': '0.9', 'iop_od': 14.0,
                                'iop_os': 15.0})
                exam_rec.with_user(doctor).action_start()
            elif state == 'done':
                exam_rec = event._oph_get_or_create_exam()
                exam_rec.write({'technician_id': benitez.id, 'va_cc_od': '0.8', 'va_cc_os': '0.9', 'iop_od': 17.0,
                                'iop_os': 16.0, 'cup_disc_od': 0.7, 'cup_disc_os': 0.6,
                                'diagnosis_ids': [(0, 0, {'diagnosis_id': diag('diagnosis_h40_1').id, 'eye': 'ou'})],
                                'plan': "<p>Estable. Continuar latanoprost.</p>"})
                exam_rec.with_user(doctor).action_start()
                exam_rec.with_user(doctor).action_done()
            else:
                event.oph_state = state

        # ------------------------------------------------------------ insurance services of last month + settlement
        first_day = today.replace(day=1) - relativedelta(months=1)
        claims = self.env['oph.insurance.claim'].search([('state', '=', 'to_bill')])
        for index, claim in enumerate(claims):
            claim.date = first_day + timedelta(days=(index * 3) % 27)
        settlement = self.env['oph.insurance.settlement'].create({
            'insurance_id': pami.id, 'date_from': first_day, 'date_to': today.replace(day=1) - timedelta(days=1)})
        settlement.action_load_claims()

        ICP.set_param('odossey_ophthalmology.demo_loaded', '1')
        return patients
