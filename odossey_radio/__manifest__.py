{
    'name': 'Odossey || Radio',
    'version': '19.0.1.0.0',
    'category': 'Sales/Radio',
    'author': 'Odossey',
    'website': 'odossey.com',
    'summary': 'Radio station management: programming grid, advertising contracts, '
               'daily log, broadcast certificates, agencies and ENACOM (Argentina)',
    'description': """
Radio station management (Community only)
=========================================
* Programming grid: programs, hosts, dayparts and commercial breaks (tandas) with capacity.
* Rate card: advertising formats (spots, mentions, PNT, sponsorships...) as products.
* Advertising orders (sale orders) that become recurring contracts (OCA subscriptions).
* Daily log (pauta) generated from the contracts, respecting the break capacity and the
  legal limit of advertising minutes per hour, with material rotation.
* Broadcast confirmation and broadcast certificates (PDF) for advertisers and agencies.
* Monthly invoicing (fixed or by aired spots) with ARCA service dates, agency commissions,
  barter and official advertising, suspension of overdue advertisers.
* Reports: break occupancy, revenue by program / format / salesperson, ENACOM fee base.
* Advertiser portal: contracts, upcoming spots and certificates.
""",
    'depends': [
        'sale_management',
        'crm',
        'contacts',
        'portal',
        'account',
        'l10n_ar',
        'subscription_oca',
        'subscription_oca_crm',
    ],
    'data': [
        'security/radio_security.xml',
        'security/ir.model.access.csv',
        'data/radio_data.xml',
        'data/ir_cron_data.xml',
        'wizard/radio_schedule_generate_views.xml',
        'wizard/radio_certificate_wizard_views.xml',
        'wizard/radio_commission_settle_views.xml',
        'views/radio_program_views.xml',
        'views/radio_config_views.xml',
        'views/radio_material_views.xml',
        'views/radio_emission_views.xml',
        'views/sale_subscription_views.xml',
        'views/sale_order_views.xml',
        'views/product_template_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'report/radio_report_views.xml',
        'report/radio_reports.xml',
        'report/radio_certificate_templates.xml',
        'report/radio_log_templates.xml',
        'report/radio_order_templates.xml',
        'report/radio_grid_templates.xml',
        'data/mail_template_data.xml',
        'views/portal_templates.xml',
        'views/radio_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odossey_radio/static/src/scss/radio.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'AGPL-3',
}
