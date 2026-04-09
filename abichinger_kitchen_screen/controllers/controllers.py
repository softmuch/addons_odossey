# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from os import path
import xml.etree.ElementTree as ET


class PosKitchenScreen(http.Controller):
    # TODO: add response types

    @http.route("/abichinger_kitchen_screen/dashboard", auth="user", website=True)
    def dashbaord(self, **kw):
        return request.render("abichinger_kitchen_screen.dashboard")

    @http.route("/abichinger_kitchen_screen/app", auth="user")
    def kitchen_screen_app(self, ks=False, **kw):
        index_path = path.join(path.dirname(__file__), "../static/app/index.html")
        return self.render_vue_app(index_path, ks, **kw)
    
    def _fetch_modules(self, names: list[str]):
        modules = request.env['ir.module.module'].search_read([('state', '=', 'installed'), ('name', 'in', names)], ["id", "name", "display_name", "installed_version", "latest_version"])
        return { mod['name']:mod for mod in modules }

    def render_vue_app(self, index_path: str, ks=False, **kw):
        # CREDIT: addons/point_of_sale/controllers/main.py
        is_internal_user = request.env.user.has_group('base.group_user')
        if not is_internal_user or not ks:
            return request.not_found()
        
        redirect_url = '/web#action=abichinger_kitchen_screen.action_kitchen_screen'
        if not ks:
            return request.redirect(redirect_url)

        kitchen_id = request.env['ab_pos.kitchen_screen'].sudo().browse(int(ks))
        if not kitchen_id:
            return request.redirect(redirect_url)

        company = kitchen_id.company_id
        session_info = request.env["ir.http"].session_info()
        session_info["user_context"]["allowed_company_ids"] = company.ids
        session_info["user_companies"] = {
            "current_company": company.id,
            "allowed_companies": {
                company.id: session_info["user_companies"]["allowed_companies"][
                    company.id
                ]
            },
        }
        session_info["nomenclature_id"] = company.nomenclature_id.id
        # session_info["fallback_nomenclature_id"] = (
        #     pos_session._get_pos_fallback_nomenclature_id()
        # )

        delivery_locs = None
        if request.env.get('ab_pos.delivery_loc') is not None:
            delivery_locs = kitchen_id.config_ids.ab_self_order_delivery_locs

        context = {
            "session_info": session_info,
            "kitchen": {
                "id": kitchen_id.id,
                "name": kitchen_id.name,
                "config_ids": kitchen_id.config_ids.ids,
                "channel": kitchen_id._get_bus_channel_name(),
                "wait_time": kitchen_id.wait_time,
                "orderline_groups": kitchen_id.orderline_group_ids._load_data(),
                **({"delivery_time": delivery_locs[0].delivery_time} if delivery_locs else {})
            },
            "ab_modules": self._fetch_modules(['abichinger_kitchen_screen', 'abichinger_pos_stock', 'ab_pos_order_status', 'ab_pos_self_order_checkout']),
        }

        # only inject script tags
        assets = http.request.render(
            "abichinger_kitchen_screen.kitchen_assets", context
        ).render()
        root = ET.fromstring(assets)
        tags = []
        for child in root:
            if child.tag != "script":
                continue
            tags.append(ET.tostring(child, encoding="unicode", method="html"))

        # load and format index.html
        with open(index_path, "r") as f:
            index_html = f.read().format(odoo_assets="".join(tags))
            return http.Response(index_html)
