import sys
from t_common import *
OUT = f'{SP}/manual'
def snap(page, name, full=False, clip=None):
    page.wait_for_timeout(1200)
    page.screenshot(path=f'{OUT}/{name}.png', full_page=full, clip=clip)
    print('shot', name)

def tab(page, name):
    page.locator(f'.o_notebook a.nav-link[name={name}]').click(); page.wait_for_timeout(700)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={'width': 1440, 'height': 900}, locale='es-AR', device_scale_factor=1.25)
    page = ctx.new_page()
    page.goto(BASE + '/web/login'); page.fill('input[name=login]', 'admin'); page.fill('input[name=password]', 'admin')
    page.click('form.oe_login_form button[type=submit]'); page.wait_for_url('**/odoo**'); page.wait_for_timeout(1500)
    trip = lambda w: sr(page, 'travel.trip', [['name', '=like', w + '%']], ['id'])[0]['id']
    so = lambda domain: sr(page, 'sale.order', domain, ['id'])[0]['id']
    page.goto(BASE + '/odoo'); page.wait_for_timeout(2500); snap(page, 'b01_apps')
    goto_action(page, 'odossey_travel.travel_trip_action'); snap(page, 'b02_trips_kanban')
    page.goto(BASE + '/odoo/action-odossey_travel.travel_trip_action?view_type=list'); wait_idle(page); snap(page, 'b02b_trips_list')
    pp = trip('Puerto Plata')
    goto_record(page, 'travel.trip', pp); snap(page, 'b03_trip_form')
    for t in ('payments', 'itinerary', 'passengers', 'summary', 'quotation', 'website'):
        goto_record(page, 'travel.trip', pp); tab(page, t); page.mouse.wheel(0, 450); snap(page, f'b04_trip_tab_{t}')
    goto_record(page, 'travel.trip', pp); click_name(page, 'action_view_calendar'); page.wait_for_timeout(2500); snap(page, 'b05_calendar')
    page.goto(BASE + '/odoo/action-odossey_travel.travel_activity_action?view_type=calendar'); wait_idle(page); page.wait_for_timeout(1500); snap(page, 'b05b_calendar_general')
    goto_action(page, 'odossey_travel.travel_booking_action'); snap(page, 'b06_bookings')
    page.click('.o_group_header:has-text("Puerto Plata")'); page.wait_for_timeout(1500); snap(page, 'b06b_bookings_open')
    fam = so([['partner_id.name', '=', 'Juan Pérez']])
    goto_record(page, 'sale.order', fam); snap(page, 'b07_booking_form')
    page.locator('.o_notebook a.nav-link').filter(has_text='Viaje').first.click(); page.wait_for_timeout(800); snap(page, 'b07b_booking_travel_tab')
    # new booking -> deposit wizard (then removed)
    goto_record(page, 'travel.trip', trip('Cataratas')); click_name(page, 'action_new_booking'); page.wait_for_selector('.o_form_view .o_field_widget[name=partner_id]')
    m2o(page, 'partner_id', 'Julieta Paz'); form_save(page); click_name(page, 'action_travel_load_services', '.o_form_statusbar')
    snap(page, 'b08_new_booking')
    nid = int(page.url.rstrip('/').split('/')[-1])
    click_name(page, 'action_confirm', '.o_form_statusbar')
    click_name(page, 'action_travel_register_deposit', '.o_form_statusbar'); page.wait_for_selector('.modal .o_field_widget[name=fixed_amount]')
    snap(page, 'b09_deposit_wizard'); close_modal(page)
    click_name(page, 'action_travel_cancel_booking', '.o_form_statusbar'); page.wait_for_selector('.modal .o_field_widget[name=reason]')
    page.locator('.modal .o_field_widget[name=reason] input').fill('Cambio de planes'); page.wait_for_timeout(800)
    snap(page, 'b10_cancel_wizard'); close_modal(page)
    rpc(page, 'sale.order', 'action_cancel', [[nid]]); rpc(page, 'sale.order', 'action_draft', [[nid]]); rpc(page, 'sale.order', 'unlink', [[nid]])
    # cancelled booking with penalty (Iguazú, Pablo)
    goto_record(page, 'sale.order', so([['partner_id.name', '=', 'Pablo Ruiz'], ['trip_id.name', '=like', 'Cataratas%']])); snap(page, 'b11_booking_cancelled')
    g = sr(page, 'travel.group', [['name', '=', 'Amigos de la facultad']], ['id'])[0]['id']
    goto_record(page, 'travel.group', g); snap(page, 'b12_group_friends')
    g = sr(page, 'travel.group', [['name', '=', 'Familia Pérez']], ['id'])[0]['id']
    goto_record(page, 'travel.group', g); snap(page, 'b12b_group_family')
    goto_action(page, 'odossey_travel.travel_passenger_action'); snap(page, 'b13_passengers')
    page.goto(BASE + '/odoo/action-odossey_travel.travel_document_scan_action'); page.wait_for_selector('.modal .o_travel_scan_input textarea')
    page.locator('.modal .o_travel_scan_input textarea').fill('00123456789@ACOSTA@MARTINA@F@44123456@A@15/03/1998@10/01/2020@27'); page.wait_for_timeout(2000)
    snap(page, 'b14_scan_dni'); close_modal(page)
    juan = sr(page, 'res.partner', [['name', '=', 'Juan Pérez']], ['id'])[0]['id']
    goto_record(page, 'res.partner', juan); page.locator('.o_notebook a.nav-link').filter(has_text='Viajero').first.click(); page.wait_for_timeout(800)
    snap(page, 'b15_contact_traveller')
    goto_action(page, 'odossey_travel.travel_partner_birthday_action'); snap(page, 'b16_birthdays')
    goto_action(page, 'odossey_travel.travel_crm_lead_action'); snap(page, 'b17_crm')
    goto_action(page, 'odossey_travel.travel_invoice_action'); snap(page, 'b18_invoices')
    inv = sr(page, 'account.move', [['partner_id.name', '=', 'Agro Pampa S.A.'], ['move_type', '=', 'out_invoice']], ['id'])[0]['id']
    goto_record(page, 'account.move', inv); snap(page, 'b19_invoice_A')
    goto_action(page, 'odossey_travel.travel_bill_action'); snap(page, 'b20_bills')
    goto_action(page, 'odossey_travel.travel_forecast_report_action'); snap(page, 'b21_forecast')
    goto_action(page, 'odossey_travel.travel_profitability_report_action'); snap(page, 'b22_profitability')
    goto_action(page, 'odossey_travel.travel_trip_occupancy_action'); snap(page, 'b23_occupancy')
    goto_action(page, 'odossey_travel.travel_config_settings_action'); page.wait_for_selector('button[name=action_travel_load_demo]'); page.wait_for_timeout(800)
    page.evaluate("document.querySelector('.o_setting_container, .settings')?.scrollTo(0,0)")
    snap(page, 'b24_settings')
    page.locator('button[name=action_travel_load_demo]').scroll_into_view_if_needed(); snap(page, 'b24b_settings_demo')
    pol = sr(page, 'travel.cancellation.policy', [], ['id'], limit=1)[0]['id']
    goto_record(page, 'travel.cancellation.policy', pol); snap(page, 'b25_policy')
    open(f'{OUT}/quote_trip.pdf', 'wb').write(page.request.get(BASE + f'/report/pdf/odossey_travel.report_travel_trip_quotation/{pp}').body())
    open(f'{OUT}/quote_booking.pdf', 'wb').write(page.request.get(BASE + f'/report/pdf/odossey_travel.report_travel_quotation/{fam}').body())
    open(f'{OUT}/profit.pdf', 'wb').write(page.request.get(BASE + f'/report/pdf/odossey_travel.report_travel_profitability/{pp}').body())
    # grant portal to Martina (for portal screenshots)
    mq = sr(page, 'res.partner', [['name', '=', 'Martina Quiroga']], ['id'])[0]['id']
    goto_record(page, 'res.partner', mq)
    page.locator('.o_cp_action_menus button, .o_cp_action_menus .dropdown-toggle').first.click(); page.wait_for_timeout(800)
    page.locator('.dropdown-item').filter(has_text='portal').first.click(); page.wait_for_selector('.modal'); page.wait_for_timeout(1500)
    snap(page, 'b26_portal_wizard')
    if page.locator('.modal button[name=action_grant_access]').count(): page.locator('.modal button[name=action_grant_access]').first.click(); page.wait_for_timeout(3000)
    uid = sr(page, 'res.users', [['partner_id', '=', mq]], ['id'])[0]['id']
    rpc(page, 'res.users', 'write', [[uid], {'password': 'Martina!2026'}])
    lucas = sr(page, 'sale.order', [['partner_id.name', '=', 'Lucas Moreno']], ['id', 'access_token'])[0]
    # --- website as visitor
    v = ctx.browser.new_context(viewport={'width': 1440, 'height': 900}, locale='es-AR', device_scale_factor=1.25).new_page()
    v.goto(BASE + '/viajes'); v.wait_for_timeout(2500); snap(v, 'w01_catalogue', full=True)
    v.click('.o_travel_trip_card:has-text("Puerto Plata") a.btn'); v.wait_for_timeout(2500); snap(v, 'w02_trip_page', full=True)
    v.goto(BASE + '/viajes'); v.click('.o_travel_trip_card:has-text("Florian") a.btn'); v.wait_for_timeout(2000); snap(v, 'w03_sold_out')
    v.goto(BASE + '/viajes'); v.click('.o_travel_trip_card:has-text("Cataratas") a.btn'); v.wait_for_selector('#travel_pax')
    v.select_option('#travel_pax', '2'); v.locator('form[action$="/reservar"] button[type=submit]').first.click(); v.wait_for_selector('#name')
    v.fill('#name', 'Florencia Gómez'); v.fill('#email', 'florencia.gomez@example.com'); v.fill('#phone', '+54 351 555 0456'); v.fill('#vat', '38456123')
    v.fill('input[name=passenger_1_name]', 'Nicolás Gómez'); v.fill('input[name=passenger_1_vat]', '37456124')
    v.check('#accept_conditions'); snap(v, 'w04_booking_form', full=True)
    v.click('.o_travel_booking_submit'); v.wait_for_timeout(4000); v.wait_for_selector('.modal.show'); snap(v, 'w05_payment_modal')
    wid = int(v.url.split('/my/orders/')[1].split('?')[0])
    v.goto(BASE + f'/my/orders/{lucas["id"]}?access_token={lucas["access_token"]}'); v.wait_for_timeout(2500); snap(v, 'w06_order_deposit_paid', full=True)
    v.goto(BASE + '/viajes/arrepentimiento'); v.wait_for_timeout(2000); snap(v, 'w07_withdrawal')
    # portal as Martina
    v.goto(BASE + '/web/login'); v.fill('input[name=login]', 'martina.quiroga@example.com'); v.fill('input[name=password]', 'Martina!2026')
    v.click('form.oe_login_form button[type=submit]'); v.wait_for_timeout(3000)
    v.goto(BASE + '/my'); v.wait_for_timeout(2500); snap(v, 'w08_portal_home')
    v.goto(BASE + '/my/trips'); v.wait_for_timeout(2500); snap(v, 'w09_my_trips')
    # remove the example web quotation
    rpc(page, 'sale.order', 'action_cancel', [[wid]])
    goto_action(page, 'odossey_travel.travel_booking_action'); page.click('.o_group_header:has-text("Cataratas")'); page.wait_for_timeout(1500)
    snap(page, 'b27_online_bookings')
    b.close()
