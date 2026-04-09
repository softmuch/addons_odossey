# 2.7.0

- Fix language selection
- Update translations
- Add backend translations
- Add new languages

# 2.6.1

- Fix zoom in Safari

# 2.6.0

- Add slider to adjust zoom
- Add takeaway tag
- Add star icon to mark order as high priority
- Update status of all combo lines at once
- Fix Overview: Add same products together

# 2.5.0

- Always add combo products even if available_in_pos is not set
- Update Overview
- Show full name of categories
- Category filter: include subcategories
- Sort categories in alphabetical order
- Fix: Prevent category restriction by preparation printers
- Fix: Load epson_printer_ip

# 2.4.0

- Add print mode (img, text) for LocalPrinter
- Increase font size of printed order slip
- Update translations

# 2.3.0

- Custom Filter: Filter orders according to specified criteria
- Enable/Disable product attributes

# 2.2.0

- Add field "Current wait time" to Kitchen Screen
- Fix tracking number of kiosk/mobile orders
- Show customer name, phone and street

# 2.1.2

- Fix kitchen screens with "All PoS"

# 2.1.1

- Fix PoS not loading on Odoo version >= [0c8f0d730465028657ff8da28e7ab14e2df08f69](https://github.com/odoo/odoo/commit/0c8f0d730465028657ff8da28e7ab14e2df08f69)
- Minor fixes

# 2.1.0

- Support multiple PoS sessions
- Refactor code to set product availability
- Update description in app store
- Set title of page's tab
- Minor fixes and improvements

# 2.0.3

- Fix duplicate order changes
- Group order items by their UUID
- Fix Kitchen Note updates

# 2.0.2

- Make self orders identifiable
- Refactor code to send POS_ORDER_CHANGE notificatons

# 2.0.1

- Fix Self-Order screen not opening

# 2.0.0

- Migrate to Odoo 18.0
- Fix print dialog on mobile

# 1.7.4

- Show a warning if websocket is disconnected
- Add link to websocket configuration example

# 1.7.3

- Fix missing module @point_of_sale/app/utils/html-to-image

# 1.7.2

- Fix default value of Kitchen Screen in POS Config
- Add demo data

# 1.7.1

- Add link to Order Status Screen
- Fix page title

# 1.7.0

- Add option to configure number of visible order stages
- Add hide button to done orders
- Reset availability filter on close
- Only show active tables in autocomplete
- Minor fixes and improvements

# 1.6.4

- Improve performance
- Fix infinite scroll of orders

# 1.6.3

- Add option to cleanup database (Settings -> Cleanup)

# 1.6.2

- Add availability filter to products view
- Fix: enable/disable dishes in self-order

# 1.6.1

- Support product attributes
- Add time formats to settings
- Add neutral edit pen
- Minor fixes and improvements

# 1.6.0

- activate/deactivate individuall dishes
  requires abichinger_pos_stock to be installed
- Fix products which no longer appear in POS
- Fix: show ready button only if is restaurant

# 1.5.2

- Add local printer

# 1.5.1

- Adjust cancellation notice to show red icon if qty has been reduced
  - Show red basket if total qty <= 0
  - Show red edit pen if total qty > 0
- Add autocomplete to search
- Increase contrast between red and orange highlight

# 1.5.0

- Add print button, supports the following printers:
  1. Point of Sale ‣ Settings ‣ ePos Printer
  2. Point of Sale ‣ Settings ‣ Kitchen Printers
- Add search
- Add option to configure preparation time colors
- Improve settings ui

# 1.4.1

- Fix red dot on internal note
- Add order by tracking number
- Fix order of orders
- Fix username in multi employee mode
- Increase size of tags
- Improve performance (use infinity scroll)

# 1.4.0

- Add option to merge order changes
- Change history for order lines
- Set color of card header
- Re-add name of waiter
- Minor fixes and improvements

# 1.3.0

- Add canceled orders
- Add notification sounds to settings
- fix sync between kitchen screen and pos screen
  the cashier could overwrite the kitchen's progress if they don't close and reopen the order

# 1.2.1

- Fix: temporarily remove username from order change
- Use web.assets_backend instead of point_of_sale._assets_pos

# 1.2.0

- Fix order count
- Include paid orders
- Add version number inside the settings drawer
- Add button to reset settings
- Reimplement interface between kitchen screen and backend

# 1.1.0

- Add tooltips

# 1.0.1

- Add favicon and title
- Fix sync between kitchen screens
- Update banner

# 1.0.0

- initial release
