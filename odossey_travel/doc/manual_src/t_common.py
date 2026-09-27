import json
import sys
import traceback
from playwright.sync_api import sync_playwright  # noqa: F401

SP = '/tmp/claude-1000/-home-yamil-odoo-envs-odoo-19/a9f6a8e9-9aed-4d79-9189-69b5103fbd97/scratchpad'
BASE = 'http://localhost:8072'
RESULTS = f'{SP}/results.jsonl'
errors = []
SUITE = sys.argv[0].rsplit('/', 1)[-1].replace('.py', '')


def record(name, ok, detail=''):
    line = {'suite': SUITE, 'test': name, 'ok': bool(ok), 'detail': str(detail)[:300]}
    with open(RESULTS, 'a') as f:
        f.write(json.dumps(line, ensure_ascii=False) + '\n')
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''))


def check(name, cond, detail=''):
    record(name, cond, detail)
    return cond


def step(name, fn, *args, **kw):
    """Run a UI step; record FAIL with the exception instead of stopping the suite."""
    try:
        res = fn(*args, **kw)
        return res
    except Exception as e:  # noqa: BLE001
        record(name, False, f"{type(e).__name__}: {e}".splitlines()[0])
        traceback.print_exc(limit=1)
        return None


def new_page(p, login='admin', password='admin', lang='es-AR'):
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={'width': 1500, 'height': 950}, locale=lang)
    page = ctx.new_page()
    page.on('pageerror', lambda e: errors.append(f"pageerror: {e}"))
    page.on('console', lambda m: errors.append(f"console: {m.text}")
            if m.type == 'error' and 'favicon' not in m.text else None)
    page.on('dialog', lambda d: d.dismiss())
    if login:
        page.goto(BASE + '/web/login')
        page.fill('input[name=login]', login)
        page.fill('input[name=password]', password)
        page.click('form.oe_login_form button[type=submit]')
        page.wait_for_url('**/odoo**', timeout=30000)
        page.wait_for_timeout(1000)
    return b, page


def shot(page, name, full=False):
    page.wait_for_timeout(800)
    page.screenshot(path=f"{SP}/shots/{name}.png", full_page=full)


def rpc(page, model, method, args, kwargs=None):
    res = page.evaluate("""async ([model, method, args, kwargs]) => {
        const r = await fetch('/web/dataset/call_kw', {method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {model, method, args, kwargs}})});
        const j = await r.json(); return j.error ? {__error: j.error.data ? j.error.data.message : j.error.message} : j.result; }""",
                        [model, method, args, kwargs or {}])
    if isinstance(res, dict) and '__error' in res:
        raise RuntimeError(res['__error'])
    return res


def sr(page, model, domain, fields, **kw):
    return rpc(page, model, 'search_read', [domain], dict(fields=fields, **kw))


def wait_idle(page, timeout=30000):
    page.wait_for_load_state('domcontentloaded')
    page.wait_for_selector('.o_action_manager > *', timeout=timeout)
    page.wait_for_timeout(1200)


def goto_action(page, xmlid, res_id=None):
    page.goto(BASE + f'/odoo/action-{xmlid}' + (f'/{res_id}' if res_id else ''))
    wait_idle(page)


def goto_record(page, model, res_id):
    page.goto(BASE + f'/odoo/{model}/{res_id}')
    page.wait_for_selector('.o_form_view', timeout=30000)
    page.wait_for_timeout(1200)


def click_name(page, name, scope=''):
    loc = page.locator(f'{scope} button[name="{name}"]:visible').first
    loc.click()
    page.wait_for_timeout(1500)


def modal_confirm(page):
    page.wait_for_selector('.modal .modal-footer .btn-primary', timeout=15000)
    page.locator('.modal .modal-footer .btn-primary').first.click()
    page.wait_for_timeout(2000)


def has_error_dialog(page):
    return page.locator('.o_error_dialog, .o_dialog .text-danger:has-text("Error")').count() > 0


def error_text(page):
    loc = page.locator('.modal .modal-body')
    return loc.first.inner_text() if loc.count() else ''


def close_modal(page):
    if page.locator('.modal .btn-close').count():
        page.locator('.modal .btn-close').first.click()
        page.wait_for_timeout(800)


def form_save(page):
    btn = page.locator('.o_form_button_save:visible')
    if btn.count():
        btn.first.click()
        page.wait_for_timeout(1500)


def m2o(page, field, text, scope=''):
    inp = page.locator(f'{scope} .o_field_widget[name={field}] input').first
    inp.click()
    inp.fill(text)
    page.wait_for_timeout(1200)
    item = page.locator('.o-autocomplete--dropdown-item:not(.o_m2o_dropdown_option)').filter(has_text=text)
    item.first.wait_for(timeout=10000)
    item.first.click()
    page.wait_for_timeout(1000)


def finish(b):
    real = [e for e in errors if 'Failed to load resource' not in e]
    check('no JS errors', not real, '; '.join(real[:3]))
    b.close()
