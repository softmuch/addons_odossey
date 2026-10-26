from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    oph_auto_billing = fields.Boolean(
        string="Bill When Closing an Exam", config_parameter='odossey_ophthalmology.auto_billing', default=True,
        help="When the ophthalmologist closes an exam its charges are billed: the services covered by the health "
             "insurance go to the monthly settlement and the co-payment or private price becomes a quotation for the "
             "patient. Example: OSDE patient with consultation + OCT → 2 insurance services and a quotation with the "
             "co-payments.")
    oph_iop_threshold = fields.Integer(
        string="High Pressure From (mmHg)", config_parameter='odossey_ophthalmology.iop_threshold', default=21,
        help="Pressures above this value are highlighted in red in the exam and in the evolution chart. Example: 21.")
    oph_demo_loaded = fields.Boolean(compute='_compute_oph_demo_loaded')

    def _compute_oph_demo_loaded(self):
        loaded = bool(self.env['ir.config_parameter'].sudo().get_param('odossey_ophthalmology.demo_loaded'))
        for rec in self:
            rec.oph_demo_loaded = loaded

    def action_oph_load_demo(self):
        self.env['oph.demo'].load_demo()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'success', 'sticky': False,
                       'message': _("Demo data loaded: professionals, patients, appointments, exams, studies, "
                                    "surgeries, prescriptions and insurance services."),
                       'next': {'type': 'ir.actions.client', 'tag': 'reload'}},
        }
