from t_common import *
OUT = f'{SP}/manual'
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(viewport={'width': 1440, 'height': 900}, locale='es-AR', device_scale_factor=1.25).new_page()
    page.goto(BASE + '/web/login'); page.fill('input[name=login]', 'admin'); page.fill('input[name=password]', 'admin')
    page.click('form.oe_login_form button[type=submit]'); page.wait_for_url('**/odoo**'); page.wait_for_timeout(1500)
    goto_action(page, 'odossey_travel.travel_passenger_action')
    page.click('.o_group_header:has-text("Puerto Plata")'); page.wait_for_timeout(1500)
    page.screenshot(path=f'{OUT}/b13_passengers.png')
    page.goto(BASE + '/odoo/action-odossey_travel.travel_document_scan_action'); page.wait_for_selector('.modal .o_travel_scan_input textarea')
    page.locator('.modal .o_travel_scan_input textarea').fill('00123456789@ACOSTA@MARTINA@F@44123456@A@15/03/1998@10/01/2020@27'); page.wait_for_timeout(2500)
    page.screenshot(path=f'{OUT}/b14_scan_dni.png')
    b.close()
