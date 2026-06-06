from odoo import fields, models


class OdosseyPosUserPrinter(models.Model):
    _name = 'odossey.pos.user.printer'
    _description = 'POS User Printer Assignment'

    config_id = fields.Many2one(
        'pos.config', string='POS Config', required=True, ondelete='cascade', index=True
    )
    user_id = fields.Many2one(
        'res.users', string='User', required=True
    )
    printer_id = fields.Many2one(
        'pos.printer', string='Preparation Printer', required=True
    )
    receipt_printer_id = fields.Many2one(
        'pos.printer', string='Receipt Printer'
    )

    _sql_constraints = [
        (
            'unique_user_per_config',
            'UNIQUE(config_id, user_id)',
            'Each user can only have one printer per POS configuration.',
        )
    ]
