from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _visible_menu_ids(self, debug=False):
        """Scope "Veterinary Only": the other apps disappear from the home screen and the menu bar (only the menus;
        what the user may read or change still depends on the access rights of the user). Being the only app, the web
        client opens it after login, on the first screen the role may use (agenda, pharmacy...)."""
        visible = super()._visible_menu_ids(debug)
        if self.env.su or not self.env.user.has_group('odossey_veterinary.group_vet_scope_vet_only'):
            return visible
        root = self.env.ref('odossey_veterinary.menu_vet_root', raise_if_not_found=False)
        if not root:
            return visible
        prefix = '%s/' % root.id
        menus = self.sudo().browse(visible)
        return frozenset(menu.id for menu in menus if (menu.parent_path or '').startswith(prefix))
