{
    'name': 'Odossey || Timesheet To Invoice - Printed Hours Variation',
    'version': '19.0.1.0.0',
    'category': 'Services/Timesheets',
    'author': 'Odossey',
    'website': 'odossey.com',
    'summary': 'Print the hours of quotations and invoices with a variation of a few '
               'minutes per entry, keeping the totals and the amounts unchanged',
    'description': """
Printed Hours Variation
=======================
Only in the "PDF Quote + Hours" and "Invoice PDF + Hours" reports, the duration of
each timesheet is printed with a variation of a few minutes (+/- 5 by default).

* The variations of each sales order line add up to zero: the totals of hours are
  the same, quantities, prices and amounts are never touched.
* The timesheets themselves are not modified.
* The variation is generated the first time the report is printed and stored on
  the sales order line (and copied to the invoice line), so printing again gives
  the same document. It is generated again only for the hours that changed.
""",
    'depends': ['odossey_timesheet_to_invoice'],
    'data': [
        'views/res_config_settings_views.xml',
        'report/timesheet_hours_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
