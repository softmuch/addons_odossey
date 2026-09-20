{
    'name': 'Odossey || POS Restaurant Fixes',
    'version': '18.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Crash fixes for stock pos_restaurant (TicketScreen blank screen)',
    'description': """
Fixes for Odoo 18 stock pos_restaurant crashes that leave the POS blank:

* TicketScreen / Órdenes -> Pagado: paid orders on tables whose floor is
  archived, not loaded in the POS or missing crash getTable()/getName()
  (table.floor_id.name on undefined).
* Órdenes -> click a paid order with no current order (e.g. coming from the
  floor plan or after a reload): PosStore.getOrderChanges(undefined) crashes
  the Refund ActionpadWidget.
""",
    'depends': ['point_of_sale', 'pos_restaurant'],
    'assets': {
        'point_of_sale._assets_pos': [
            'odossey_pos_restaurant_fixes/static/src/js/restaurant_fixes.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
