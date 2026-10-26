{
    'name': 'Odossey || Ophthalmology',
    'version': '19.0.1.0.0',
    'category': 'Services/Ophthalmology',
    'author': 'Odossey',
    'website': 'odossey.com',
    'license': 'LGPL-3',
    'summary': 'Ophthalmology clinic: agenda and waiting room, eye exam per eye (OD/OS), studies, glasses and drug '
               'prescriptions, surgery with IOL traceability, consents, health insurance billing and patient portal',
    'description': """
Ophthalmology clinic management (Odoo Community only)
=====================================================
* Patients with clinical record number, ID, health insurance (obra social / prepaga / PAMI), plan and member number,
  allergies and systemic risk factors with alert banners.
* Agenda by professional with appointment types, rooms and a waiting room board (booked, arrived, pre-consultation,
  in consultation, done) with waiting times; reminders by email and WhatsApp.
* Eye exam per eye (right / left): visual acuity, auto-refraction, subjective refraction, keratometry, intraocular
  pressure, pachymetry, slit lamp, fundus with cup/disc ratio, motility and pupils, ICD-10 diagnoses, plan and
  follow-up control. Warnings for high pressure.
* Complementary studies (OCT, visual field, topography, biometry, retinography, angiography, ultrasound...) with
  per-eye results and report.
* Glasses and contact lens prescriptions generated from the refraction; drug prescriptions with professional license
  (Law 27.553); integrity fingerprint on every issued document.
* Surgery planning: procedure, eye, surgeon, operating room (no overlaps), insurance authorization, pre-operative
  checklist, intraocular lens with lot / serial traceability, surgical protocol, implant card and post-operative
  controls.
* Informed consents signed on screen or from the portal (Law 26.529); certificates (driving licence, school, rest).
* Billing: private patients through quotations and invoices; health insurance services (nomenclator codes, coverage
  and co-payment, authorization) grouped in monthly settlements invoiced to each insurer.
* Patient portal: appointments, prescriptions, study reports, certificates and consent signature.
* Argentine master data (ICD-10 eye diagnoses, studies, procedures, eye drops, intraocular lenses, insurers) in
  English, Spanish and Italian. Demo data on demand from the settings.
""",
    'depends': [
        'mail',
        'contacts',
        'portal',
        'calendar',
        'sale_management',
        'sale_stock',
        'product_expiry',
        'purchase',
        'account',
    ],
    'data': [
        'security/oph_security.xml',
        'security/ir.model.access.csv',
        'data/oph_data.xml',
        'data/oph_product_data.xml',
        'data/oph_master_data.xml',
        'views/oph_master_views.xml',
        'wizard/oph_price_update_views.xml',
        'views/oph_insurance_views.xml',
        'views/res_partner_views.xml',
        'views/calendar_event_views.xml',
        'views/oph_exam_views.xml',
        'views/oph_study_views.xml',
        'views/oph_prescription_views.xml',
        'views/oph_surgery_views.xml',
        'views/oph_document_views.xml',
        'views/oph_billing_views.xml',
        'views/res_config_settings_views.xml',
        'views/portal_templates.xml',
        'report/oph_reports.xml',
        'views/oph_menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
}
