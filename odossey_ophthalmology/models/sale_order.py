from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    oph_exam_id = fields.Many2one('oph.exam', string="Exam", index='btree_not_null', copy=False)
    oph_surgery_id = fields.Many2one('oph.surgery', string="Surgery", index='btree_not_null', copy=False)
    oph_study_id = fields.Many2one('oph.study', string="Study", index='btree_not_null', copy=False)
    oph_patient = fields.Boolean(related='partner_id.is_oph_patient', string="Ophthalmology Patient")

    def _action_confirm(self):
        res = super()._action_confirm()
        self._oph_assign_lots()
        return res

    def _oph_assign_lots(self):
        """The lens / supply lot chosen in the clinic is the one delivered: the picking is prepared with it."""
        charges = self.env['oph.charge'].search([('sale_line_id', 'in', self.order_line.ids), ('lot_id', '!=', False)])
        for charge in charges:
            moves = charge.sale_line_id.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
            for move in moves:
                move.move_line_ids.unlink()
                self.env['stock.move.line'].create({
                    'move_id': move.id, 'product_id': move.product_id.id, 'lot_id': charge.lot_id.id,
                    'quantity': move.product_uom_qty, 'product_uom_id': move.product_uom.id,
                    'location_id': move.location_id.id, 'location_dest_id': move.location_dest_id.id,
                    'picking_id': move.picking_id.id,
                })
