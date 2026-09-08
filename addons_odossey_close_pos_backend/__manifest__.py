{
    'name': 'Odossey || Cerrar Caja Registradora desde Backend',
    'version': '19.0.1.0.0',
    'category': 'Point of Sale',
    'author': 'Odossey',
    'website': 'odossey.com',
    'summary': 'Agrega botón para cerrar la caja registradora directamente desde la vista kanban de Punto de Venta',
    'description': """
Agrega un botón "Cerrar caja registradora" en la vista kanban de configuraciones
de Punto de Venta (point_of_sale.view_pos_config_kanban), al lado del botón
"Continue Selling" / "Open Register", que abre la sesión de POS y dispara
automáticamente el popup nativo de cierre de caja (ClosePosPopup), exactamente
el mismo proceso de conteo/validación que al cerrar desde el propio POS.
""",
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_config_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'addons_odossey_close_pos_backend/static/src/overrides/pos_store.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
