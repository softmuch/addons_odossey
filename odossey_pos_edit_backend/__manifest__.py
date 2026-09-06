# -*- coding: utf-8 -*-
{
    'name': 'Odossey POS - Edición Backend y Pago Libre',
    'version': '1.0',
    'summary': 'Reabrir/editar pos.order desde el backend (líneas, impuestos, pagos), '
               'reconfirmar generando picking de corrección, y pagar libremente '
               '(back y front) aplicando un importe a las órdenes POS abiertas del cliente',
    'description': """
Odossey POS - Edición Backend y Pago Libre
===========================================
Extraído de odoxeus_rioseed para no acoplar la localización RioSeed a estas
funcionalidades genéricas de POS:

- Reapertura a borrador de una orden pagada/registrada/parcialmente pagada
  ("Volver a Borrador"), con snapshot de cantidades por producto.
- Edición de líneas/pagos/impuestos mientras la orden está en borrador.
- Reconfirmación ("Confirmar") que compara el snapshot contra las líneas
  actuales y genera picking(s) de corrección por la diferencia de cantidad.
- Pago libre: aplica un importe a las órdenes POS abiertas más viejas de un
  cliente, tanto desde el backend (lista de órdenes) como desde el frontend
  del POS (botón "Pagar Libremente" en Acciones).
    """,
    'category': 'Point of Sale',
    'author': 'Odossey',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base', 'point_of_sale', 'l10n_latam_check_ext', 'odossey_partial_payments_pos',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/pay_freely_wizard_view.xml',
        'views/pos_order_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'odossey_pos_edit_backend/static/src/app/components/pay_freely_popup/pay_freely_popup.js',
            'odossey_pos_edit_backend/static/src/app/components/pay_freely_popup/pay_freely_popup.xml',
            'odossey_pos_edit_backend/static/src/app/screens/product_screen/control_buttons/control_buttons_patch.js',
            'odossey_pos_edit_backend/static/src/app/screens/product_screen/control_buttons/control_buttons_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
