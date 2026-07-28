from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _compute_quantities_dict(self, lot_id, owner_id, package_id, from_date=False, to_date=False):
        # Kit availability (qty_available/virtual_available/...) is computed by
        # exploding the full BoM tree (mrp's override of this method), one
        # mrp.bom search per BoM line discovered. That's fine for a single
        # product (e.g. its form view) but explodes into thousands of queries
        # when reading many products at once (product list/kanban), especially
        # with nested kits (a kit whose component is itself a kit).
        #
        # For batch reads we skip the kit explosion and report 0 instead -
        # kits simply show no on-hand quantity in list/kanban views. Single-
        # record reads (form view, smart buttons) are unaffected and keep the
        # real computed value.
        if len(self) <= 1:
            return super()._compute_quantities_dict(
                lot_id, owner_id, package_id, from_date=from_date, to_date=to_date)

        kits = self.filtered('is_kits')
        if not kits:
            return super()._compute_quantities_dict(
                lot_id, owner_id, package_id, from_date=from_date, to_date=to_date)

        others = self - kits
        res = (
            super(ProductProduct, others)._compute_quantities_dict(
                lot_id, owner_id, package_id, from_date=from_date, to_date=to_date)
            if others else {}
        )
        for kit in kits:
            res[kit.id] = dict.fromkeys(
                ['qty_available', 'free_qty', 'incoming_qty', 'outgoing_qty', 'virtual_available'], 0.0,
            )
        return res
