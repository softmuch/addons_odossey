{
    'name': 'Odossey || Timesheet To Invoice',
    'version': '19.0.1.0.0',
    'category': 'Services/Timesheets',
    'author': 'Odossey',
    'website': 'odossey.com',
    'summary': 'Mark timesheets as billable or maintenance, split quantities on '
               'sales and invoices and print quotations / invoices with their hours',
    'description': """
Timesheet To Invoice
====================
* "To Invoice" checkbox on every timesheet (checked by default).
* Sale order lines: the quantity only counts the hours to invoice, a new
  "Extra Quantity" column holds the maintenance hours that are not invoiced.
* Invoice lines: same "Extra Quantity" column.
* New "PDF Quote + Hours" and "Invoice + Hours" reports: the standard document
  followed by the detail of the hours, split in "Invoiced hours" and
  "Maintenance hours (not invoiced)".
""",
    'depends': ['sale_timesheet'],
    'data': [
        'views/hr_timesheet_views.xml',
        'views/project_task_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'report/timesheet_hours_templates.xml',
        'report/timesheet_hours_reports.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
