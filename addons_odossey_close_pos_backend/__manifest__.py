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
"Continue Selling" / "Open Register". Abre un wizard 100% backend (no navega
a /pos/ui) que llama a los mismos métodos que usa el POS para cerrar la sesión
(post_closing_cash_details, update_closing_control_state_session,
action_pos_session_closing_control), incluyendo el wizard nativo de descuadre
contable cuando corresponde.
""",
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_config_views.xml',
        'views/close_session_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
