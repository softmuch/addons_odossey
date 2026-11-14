"""Agenda settings (14/11/2026): the rooms become optional; databases that already used them keep them."""
from odoo import SUPERUSER_ID, api

from odoo.addons.odossey_veterinary.hooks import enable_rooms


def migrate(cr, version):
    enable_rooms(api.Environment(cr, SUPERUSER_ID, {}))
