# -*- coding: utf-8 -*-
# ============================================================================
#  RĪGAS TEHNISKĀ UNIVERSITĀTE
#  Bakalaura darbs — Maksims Koļcovs (231RDB363)
#
#  FAILS: testesana_pec_optimizacijas.py
#
#  Veiktspējas mērījumi PĒC custom_partner_opt moduļa instalēšanas.
#  Scenāriji ir identiski testesana.py (pirms optimizācijas), lai
#  rezultāti būtu tieši salīdzināmi 4.6. nodaļā.
#
# ============================================================================

import xmlrpc.client
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Savienojuma parametri (no odoo.conf) ──────────────────────
URL      = 'http://localhost:8069'
DB       = 'BaklauraDarbs'
USER     = 'xxxxxxxx'
PASSWORD = 'xxxxxxxx'

REQUESTS_EACH = 5  # pieprasījumi uz vienu lietotāju — identisks pirms-testam

# Meklēšanas atslēgvārdi — identiski pirms-testam
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
# Tests A: name_search() — optimizētais (2 lauki ar GIN indeksiem)
#
# Pirms optimizācijas: meklēja pa 5 laukiem ar OR ILIKE → Seq Scan
# Pēc optimizācijas:  _rec_names_search = ['complete_name', 'email'] +
#                     _search_display_name bez child_of + GIN trigrammu indeksi
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
# Tests B: search() — tikai complete_name (references tests)
#
# Identisks pirms-testam B. Izmanto kā atskaites punktu — šim testam
# optimizācija dod mazāku ieguvumu, jo jau pirms tam meklēja tikai 1 lauku.
# GIN indekss tomēr paātrina arī šo vaicājumu.
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
# Tests C: search_read() — saraksta ielāde (identisks pirms-testam)
#
# Mēra vispārējo saraksta ielādes laiku.
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
# Tests D: search_count() — filtrēšana (identisks pirms-testam)
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
# Tests E (JAUNS): search_read() ar kešotiem laukiem contact_address un
#                  email_formatted (store=True ieguvuma pārbaude)
#
# Pirms optimizācijas: contact_address un email_formatted tika pārrēķināti
#   katram ierakstam → N papildu vaicājumi uz country_id un state_id
# Pēc optimizācijas:  vērtības ir kešotas DB → viens SELECT vaicājums
#
# Sagaidāmais ieguvums: saraksta ielādes laiks ar šiem laukiem samazinās
# ─────────────────────────────────────────────────────────────────────────────
def task_e(user_id):
    uid, models = make_client()
    times = []
    for i in range(REQUESTS_EACH):
        kw = keywords[(user_id * REQUESTS_EACH + i) % len(keywords)]
        t1 = time.perf_counter()
        models.execute_kw(DB, uid, PASSWORD,
            'res.partner', 'search_read',
            [[['active', '=', True]]],
            {
                'fields': ['name', 'contact_address', 'email_formatted',
                           'email', 'phone'],
                'limit': 80,
                'offset': (user_id * REQUESTS_EACH + i) * 10 % 1000,
            })
        times.append((time.perf_counter() - t1) * 1000)
    return times


# ─────────────────────────────────────────────────────────────────────────────
# Tests F (JAUNS): write() masveida atjaunināšana — N+1 optimizācijas pārbaude
#
# Pirms optimizācijas: write() ar comment/color laukiem izsauca _fields_sync()
#   katram partnerim → N+1 vaicājumu problēma
# Pēc optimizācijas:  selektīvs _fields_sync — ja vals nesatur adreses laukus,
#   _fields_sync tiek pilnībā izlaists
#
# Tests atjaunina 'comment' lauku (nav adreses lauks) → optimizācija jāaktivizējas
# Sagaidāmais ieguvums: write() laiks samazinās proporcionāli ierakstu skaitam
# ─────────────────────────────────────────────────────────────────────────────
def task_f(user_id):
    uid, models = make_client()
    times = []

    # Iegūstam 50 partneru ID katram "lietotājam" (dažādi offset, lai nav
    # kešošanas efekts no vienādiem ierakstiem)
    partner_ids = models.execute_kw(DB, uid, PASSWORD,
        'res.partner', 'search',
        [[['active', '=', True]]],
        {'limit': 50, 'offset': user_id * 50 % 5000})

    if not partner_ids:
        return [0.0] * REQUESTS_EACH

    for i in range(REQUESTS_EACH):
        # Batch: atjauninām comment lauku (nav adreses lauks → _fields_sync
        # jāizlaiž optimizētajā kodā)
        t1 = time.perf_counter()
        models.execute_kw(DB, uid, PASSWORD,
            'res.partner', 'write',
            [partner_ids, {'comment': f'perf_test_run_{user_id}_{i}'}])
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
print("  res.partner veiktspējas tests — PĒC optimizācijas")
print(f"  Ierakstu skaits datubāzē : {count}")
print(f"  Pieprasījumi / lietotājs : {REQUESTS_EACH}")
print(f"  Scenāriji                : 3 → 20 → 50 lietotāji")
print("=" * 62)

USER_COUNTS = [3, 20, 50]

tasks = [
    (task_a, "Tests A — name_search() optimizēts (2 lauki)"),
    (task_b, "Tests B — search() complete_name"),
    (task_c, "Tests C — search_read() saraksts"),
    (task_d, "Tests D — search_count() filtri"),
    (task_e, "Tests E — search_read() kešoti lauki"),
    (task_f, "Tests F — write() N+1 optimizācija"),
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
header = f"  {'Tests':<40} {'3 lit.':>8} {'20 lit.':>8} {'50 lit.':>8}"
print(header)
print(f"  {'-'*40} {'-'*8} {'-'*8} {'-'*8}")

for _, label in tasks:
    results = all_results[label]
    short = label[:40]
    vals  = "  ".join(f"{r['mean']:>8.2f}" for r in results)
    print(f"  {short:<40} {vals}")

print(f"\n  Wall laiks (ms) — kopējais reālais laiks")
print(f"  {'-'*40} {'-'*8} {'-'*8} {'-'*8}")

for _, label in tasks:
    results = all_results[label]
    short = label[:40]
    vals  = "  ".join(f"{r['wall_ms']:>8.0f}" for r in results)
    print(f"  {short:<40} {vals}")

# ─────────────────────────────────────────────────────────────────────────────
# SALĪDZINĀJUMS AR PIRMS-OPTIMIZĀCIJAS REZULTĀTIEM (4.4.2. nodaļa)
# Šīs vērtības ir fiksētas no sākotnējā testesana.py izpildes rezultātiem
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# SALĪDZINĀJUMS AR PIRMS-OPTIMIZĀCIJAS REZULTĀTIEM (4.4.2. nodaļa)
# Šīs vērtības ir fiksētas no sākotnējā testesana.py izpildes rezultātiem
# ─────────────────────────────────────────────────────────────────────────────
before_mean = {
    "Tests A": [2232.13, 2835.37, 4584.17],
    "Tests B": [2098.81, 2421.80, 3273.19],
    "Tests C": [2086.61, 2313.48, 3529.14],
    "Tests D": [2129.72, 2666.99, 3234.40],
}

before_wall = {
    "Tests A": [14281, 18908, 31601],
    "Tests B": [13724, 16680, 24948],
    "Tests C": [13622, 16157, 26263],
    "Tests D": [13880, 17476, 25047],
}

label_map = {
    "Tests A — name_search() optimizēts (2 lauki)": "Tests A",
    "Tests B — search() complete_name":              "Tests B",
    "Tests C — search_read() saraksts":              "Tests C",
    "Tests D — search_count() filtri":               "Tests D",
}

print(f"\n{'=' * 62}")
print("  SALĪDZINĀJUMS — vidējais laiks uz pieprasījumu (ms)")
print(f"  (pozitīvs % = ātrāk; tikai A–D testiem, jo E un F ir jauni)")
print(f"{'=' * 62}")
print(f"  {'Tests':<40} {'3 lit.':>9} {'20 lit.':>9} {'50 lit.':>9}")
print(f"  {'-'*40} {'-'*9} {'-'*9} {'-'*9}")

for _, label in tasks[:4]:
    results = all_results[label]
    key = label_map.get(label)
    if not key or key not in before_mean:
        continue
    b_vals = before_mean[key]
    parts = []
    for r, b in zip(results, b_vals):
        pct = (b - r['mean']) / b * 100
        parts.append(f"{pct:>+8.1f}%")
    short = label[:40]
    print(f"  {short:<40} {'  '.join(parts)}")

print(f"\n  Wall laiks — kopējais reālais laiks")
print(f"  {'-'*40} {'-'*9} {'-'*9} {'-'*9}")

for _, label in tasks[:4]:
    results = all_results[label]
    key = label_map.get(label)
    if not key or key not in before_wall:
        continue
    b_vals = before_wall[key]
    parts = []
    for r, b in zip(results, b_vals):
        pct = (b - r['wall_ms']) / b * 100
        parts.append(f"{pct:>+8.1f}%")
    short = label[:40]
    print(f"  {short:<40} {'  '.join(parts)}")

print(f"\n{'=' * 62}")
print("  Tests pabeigts.")
print(f"{'=' * 62}")