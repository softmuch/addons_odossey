=========================================
Product Pricelist Item Reference Currency
=========================================

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/license-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3

|badge1| |badge2|

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

**Table of contents**

.. contents::
   :local:

Usage
=====

1. Go to a pricelist item where *Price Type* is *Fixed Price*.
2. Enable the *Use Reference Currency* checkbox.
3. Select the *Reference Currency* (the currency the *Fixed Price* is
   expressed in).
4. Set the *Fixed Price* in that reference currency.

The price will be converted to the pricelist's currency, based on the
reference currency's ``rate``, whenever this item is applied (sale order
lines, POS, e-commerce, etc.).

Credits
=======

Contributors
------------

- Yamil Giralda <y.giralda@huroos.com>
