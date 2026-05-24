# -*- coding: utf-8 -*-
# ============================================================================
#  RĪGAS TEHNISKĀ UNIVERSITĀTE
#  Bakalaura darbs — Maksims Koļcovs (231RDB363)
#
#  FAILS: testesana.py
#
#  Veiktspējas mērījumi PIRMS custom_partner_opt moduļa instalēšanas.
#  Šis skripts jāpalaiž ar atinstalētu custom_partner_opt moduli, lai
#  rezultāti atspoguļotu standarta Odoo 19.0 veiktspēju.
#
#  Scenāriji: 3, 20, 50 vienlaicīgi lietotāji × 5 pieprasījumi katrs.
# ============================================================================

import xmlrpc.client
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Savienojuma parametri (no odoo.conf) ──────────────────────
URL      = 'http://localhost:8069'
DB       = 'BaklauraDarbs'
USER     = 'xxxxxxx'
PASSWORD = 'xxxxxxx'

REQUESTS_EACH = 5  # pieprasījumi uz vienu lietotāju

# Reālistiski meklēšanas atslēgvārdi (5-8 simboli) — aktivizē pg_trgm
# indeksu pēc optimizācijas un atgriež nelielu rezultātu skaitu, kas
# atspoguļo reālu lietotāja meklēšanas uzvedību CRM sistēmā.
keywords = [
    'schmidt', 'johnson', 'mueller', 'andersen', 'fischer',
    'nielsen', 'bergman', 'larsson', 'petersen', 'erikson',
    'hansen', 'lindberg', 'svensson', 'karlsson', 'magnus',
    'kristian', 'wilhelm', 'frederik', 'gustavo', 'bernard',
]


def make_client():
    common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
    uid    = common.authenticate(DB, USER, PASSWORD, {})
    models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
    return uid, models


# ─────────────────────────────────────────────────────────────────────────────
# Tests A: name_search() — 5 lauki ar ILIKE (standarta Odoo)
#
# Standarta implementācija meklē pa pieciem laukiem:
# complete_name, email, ref, vat, company_registry
# Katrs pieprasījums ģenerē SQL ar 5 OR ILIKE klauzulām → Seq Scan
# ─────────────────────────────────────────────────────────────────────────────
def task_a(user_id):
    uid, models = make_client()
    times = []
    for i in range(REQUESTS_EACH):
        kw = keywords[(user_id * REQUESTS_EACH + i) % len(keywords)]
        t1 = time.perf_counter()
        models.execute_kw(DB, uid, PASSWORD,
            'res.partner', 'name_search',
            [kw], {'limit': 100})
        times.append((time.perf_counter() - t1) * 1000)
    return times


# ─────────────────────────────────────────────────────────────────────────────
# Tests B: search() — tikai complete_name
#
# Meklē tikai pa vienu lauku — kalpo kā references punkts, lai
# izolētu OR klauzulu skaita ietekmi salīdzinājumā ar Tests A.
# ─────────────────────────────────────────────────────────────────────────────
def task_b(user_id):
    uid, models = make_client()
    times = []
    for i in range(REQUESTS_EACH):
        kw = keywords[(user_id * REQUESTS_EACH + i) % len(keywords)]
        t1 = time.perf_counter()
        models.execute_kw(DB, uid, PASSWORD,
            'res.partner', 'search',
            [[['complete_name', 'ilike', kw]]],
            {'limit': 100})
        times.append((time.perf_counter() - t1) * 1000)
    return times


# ─────────────────────────────────────────────────────────────────────────────
# Tests C: search_read() — saraksta ielāde
#
# Simulē lietotāja saraksta skata ielādi ar filtrēšanu.
# Ielādē 80 ierakstus ar 6 laukiem — tipiska lappuses apjoms CRM skatā.
# ─────────────────────────────────────────────────────────────────────────────
def task_c(user_id):
    uid, models = make_client()
    times = []
    for i in range(REQUESTS_EACH):
        kw = keywords[(user_id * REQUESTS_EACH + i) % len(keywords)]
        t1 = time.perf_counter()
        models.execute_kw(DB, uid, PASSWORD,
            'res.partner', 'search_read',
            [[['complete_name', 'ilike', kw],
              ['active', '=', True]]],
            {
                'fields': ['name', 'email', 'phone',
                           'country_id', 'is_company', 'vat'],
                'limit': 80
            })
        times.append((time.perf_counter() - t1) * 1000)
    return times


# ─────────────────────────────────────────────────────────────────────────────
# Tests D: search_count() — filtrēšana
#
# Simulē dažādus filtrēšanas scenārijus (uzņēmumi, privātpersonas,
# ar e-pastu, ar PVN numuru, pēc valsts). Mēra tīro filtrēšanas laiku
# bez datu ielādes.
# ─────────────────────────────────────────────────────────────────────────────
def task_d(user_id):
    uid, models = make_client()
    times = []
    filters = [
        [['is_company', '=', True],      ['active', '=', True]],
        [['is_company', '=', False],     ['active', '=', True]],
        [['active', '=', True],          ['email', '!=', False]],
        [['active', '=', True],          ['vat', '!=', False]],
        [['country_id.code', '=', 'LV'], ['active', '=', True]],
    ]
    for i in range(REQUESTS_EACH):
        fdom = filters[i % len(filters)]
        t1 = time.perf_counter()
        models.execute_kw(DB, uid, PASSWORD,
            'res.partner', 'search_count', [fdom])
        times.append((time.perf_counter() - t1) * 1000)
    return times


# ─────────────────────────────────────────────────────────────────────────────
# Palaiž vienu scenāriju ar N lietotājiem
# ─────────────────────────────────────────────────────────────────────────────
def run_scenario(n_users, task_fn, label):
    all_times = []
    errors    = 0
    wall_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=n_users) as ex:
        futures = {ex.submit(task_fn, i): i for i in range(n_users)}
        for fut in as_completed(futures):
            try:
                all_times.extend(fut.result())
            except Exception as e:
                errors += 1
                print(f"    KĻŪDA: {e}")

    wall_ms = (time.perf_counter() - wall_start) * 1000

    return {
        'label':   label,
        'n_users': n_users,
        'mean':    statistics.mean(all_times) if all_times else 0,
        'median':  statistics.median(all_times) if all_times else 0,
        'min':     min(all_times) if all_times else 0,
        'max':     max(all_times) if all_times else 0,
        'stdev':   statistics.stdev(all_times) if len(all_times) > 1 else 0,
        'wall_ms': wall_ms,
        'total':   len(all_times),
        'errors':  errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Izdrukā viena scenārija rezultātus
# ─────────────────────────────────────────────────────────────────────────────
def print_result(r):
    print(f"    Pieprasījumi : {r['total']}")
    print(f"    Vidējais     : {r['mean']:.2f} ms")
    print(f"    Mediāna      : {r['median']:.2f} ms")
    print(f"    Min / Max    : {r['min']:.2f} / {r['max']:.2f} ms")
    print(f"    Standartnovir: {r['stdev']:.2f} ms")
    print(f"    Wall laiks   : {r['wall_ms']:.2f} ms")
    print(f"    Kļūdas       : {r['errors']}")


# ─────────────────────────────────────────────────────────────────────────────
# GALVENAIS
# ─────────────────────────────────────────────────────────────────────────────

common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
uid    = common.authenticate(DB, USER, PASSWORD, {})
models_proxy = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
count  = models_proxy.execute_kw(DB, uid, PASSWORD,
    'res.partner', 'search_count', [[]])

print("=" * 62)
print("  res.partner veiktspējas tests — pirms optimizācijas")
print(f"  Ierakstu skaits datubāzē : {count}")
print(f"  Pieprasījumi / lietotājs : {REQUESTS_EACH}")
print(f"  Scenāriji                : 3 → 20 → 50 lietotāji")
print("=" * 62)

USER_COUNTS = [3, 20, 50]

tasks = [
    (task_a, "Tests A — name_search() 5 lauki"),
    (task_b, "Tests B — search() complete_name"),
    (task_c, "Tests C — search_read() saraksts"),
    (task_d, "Tests D — search_count() filtri"),
]

all_results = {label: [] for _, label in tasks}

for task_fn, label in tasks:
    print(f"\n{'=' * 62}")
    print(f"  {label}")
    print(f"{'=' * 62}")

    for n in USER_COUNTS:
        print(f"\n  [{n} vienlaicīgi lietotāji × "
              f"{REQUESTS_EACH} pieprasījumi = "
              f"{n * REQUESTS_EACH} kopā]")
        r = run_scenario(n, task_fn, label)
        print_result(r)
        all_results[label].append(r)

# ─────────────────────────────────────────────────────────────────────────────
# KOPSAVILKUMS
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'=' * 62}")
print("  KOPSAVILKUMS — vidējais laiks uz pieprasījumu (ms)")
print(f"{'=' * 62}")
header = f"  {'Tests':<36} {'3 lit.':>8} {'20 lit.':>8} {'50 lit.':>8}"
print(header)
print(f"  {'-'*36} {'-'*8} {'-'*8} {'-'*8}")

for _, label in tasks:
    results = all_results[label]
    short = label[:36]
    vals  = "  ".join(f"{r['mean']:>8.2f}" for r in results)
    print(f"  {short:<36} {vals}")

print(f"\n  Wall laiks (ms) — kopējais reālais laiks")
print(f"  {'-'*36} {'-'*8} {'-'*8} {'-'*8}")

for _, label in tasks:
    results = all_results[label]
    short = label[:36]
    vals  = "  ".join(f"{r['wall_ms']:>8.0f}" for r in results)
    print(f"  {short:<36} {vals}")

print(f"\n{'=' * 62}")
print("  Tests pabeigts.")
print(f"{'=' * 62}")
