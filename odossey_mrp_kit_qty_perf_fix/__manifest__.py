{
    'name': 'Odossey || MRP Kit Quantity Performance Fix',
    'version': '18.0.1.0.0',
    'category': 'Manufacturing',
    'author': 'Odossey',
    'website': 'odossey.com',
    'summary': 'Stops kit-of-kit BoM explosion from making product list/kanban views extremely slow when mrp is installed',
    'description': """
Kit stock quantity (`qty_available`/`virtual_available`/...) for a kit-type
product (phantom BoM) is computed by exploding its full BoM tree, doing one
`mrp.bom` search per BoM line discovered
(mrp.models.product.ProductProduct._compute_quantities_dict). That's cheap
for a single product, but with a kit nested inside another kit this
multiplies into thousands of extra queries the moment many products are read
at once - e.g. any product list/kanban view (Inventory > Products).

This module skips that expensive kit explosion when more than one product is
being read at a time: kit products simply report 0 on-hand/forecasted
quantity in list/kanban views. Opening a single kit's form (or its BoM smart
button) is unaffected and still shows the real computed value.
""",
    'depends': ['mrp'],
    'data': [],
    'installable': True,
    'application': False,
    'license': 'OPL-1',
}
