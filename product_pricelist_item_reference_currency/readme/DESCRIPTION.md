This module allows defining, on a pricelist item whose *Price Type* is
*Fixed Price*, a **Reference Currency**. When enabled, the *Fixed Price* is
understood to be expressed in that reference currency instead of the
pricelist's currency, and it is automatically converted to the pricelist
currency (using the reference currency's rate) every time the pricelist
item is used to compute a price (e.g. when adding a product on a sale
order).

Example: reference currency USD, fixed price 10, pricelist currency ARS,
rate 1 USD = 1450 ARS -> the price applied is 14500 ARS.

If the *Use Reference Currency* option is left disabled, the pricelist
item behaves exactly as in standard Odoo: the *Fixed Price* is used as-is,
in the pricelist currency, without any conversion.
