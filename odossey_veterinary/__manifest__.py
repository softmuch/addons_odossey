{
    'name': 'Odossey || Veterinary',
    'version': '19.0.1.0.0',
    'category': 'Services/Veterinary',
    'author': 'Odossey',
    'website': 'odossey.com',
    'license': 'LGPL-3',
    'summary': 'Veterinary clinic: patients, medical record (SOAP), vaccination with reminders, prescriptions, '
               'hospitalization, consents, lab, certificates and owner portal (Community only)',
    'description': """
Veterinary clinic management (Odoo Community only)
==================================================
* Patients (pets) with owner, species, breed, microchip, weight curve, alerts and handling notes.
* Medical record per consultation (SOAP): vital signs with reference ranges, physical exam, coded diagnoses
  (zoonosis / notifiable warnings), plan, owner instructions, attachments and lab results.
* Charges of the visit turn into a quotation; vaccines and antiparasitics create the preventive record with lot,
  next dose computed from the product schedule and reminders by email and WhatsApp.
* Prescriptions: simple or archived (controlled drugs), professional license, electronic prescription code
  (CUVE, Res. SENASA 654/2026), integrity fingerprint; controlled drugs register.
* Hospitalization with an hourly treatment sheet, daily charge and discharge summary.
* Informed consents signed on screen or from the portal; health, travel, deworming and death certificates;
  rabies vaccination certificate (Law 22.953, Argentina).
* Agenda with appointment types, rooms and visit status; owner portal (pets, vaccination card, documents).
* Argentine master data: species, breeds, diseases, vaccines, medications, supplies, services and lab panels,
  translated into English, Spanish and Italian. Demo data on demand from the settings.
""",
    'depends': [
        'mail',
        'contacts',
        'portal',
        'calendar',
        'sale_management',
        'sale_stock',
        'product_expiry',
        'account',
    ],
    'data': [
        'security/vet_security.xml',
        'security/ir.model.access.csv',
        'data/vet_master_data.xml',
        'data/vet_product_data.xml',
        'data/vet_data.xml',
        'views/vet_pet_views.xml',
        'views/vet_consultation_views.xml',
        'views/vet_vaccination_views.xml',
        'views/vet_hospitalization_views.xml',
        'views/vet_document_views.xml',
        'views/vet_config_views.xml',
        'views/portal_templates.xml',
        'report/vet_reports.xml',
        'views/vet_menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
}
