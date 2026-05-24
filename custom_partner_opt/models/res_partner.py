# -*- coding: utf-8 -*-
# ============================================================================
#  RĪGAS TEHNISKĀ UNIVERSITĀTE / RIGA TECHNICAL UNIVERSITY
#  Datorzinātnes, informācijas tehnoloģijas un enerģētikas fakultāte
#  Faculty of Computer Science, Information Technology and Energy
#
#  Bakalaura darbs / Bachelor's Thesis
#  "Odoo ERP moduļa paplašināšana un pielāgošana datorsistēmu arhitektūrā"
#  "Odoo ERP module extension and customization in computer system architecture"
#
#  Autors / Author:           Maksims Koļcovs (stud. apl. nr. 231RDB363)
#  Zinātniskais vadītājs:     Mg.sc.ing. Valdis Saulespurēns
#  Scientific supervisor:     Mg.sc.ing. Valdis Saulespurēns
#  Gads / Year:               2026
# ============================================================================
#
#  FAILS / FILE: custom_partner_opt/models/res_partner.py
#
#  LV: Šis fails satur res.partner modeļa optimizāciju, kas pievieno četras
#      galvenās izmaiņas oriģinālajam Odoo 19.0 res_partner.py kodam, lai
#      uzlabotu sistēmas veiktspēju lielos datu apjomos (100 000+ ierakstu):
#
#         1. Lauku kešdarbe — store=True uz contact_address un email_formatted;
#         2. Saīsināts _rec_names_search — no 5 uz 2 indeksētiem laukiem;
#         3. Pārrakstīta _search_display_name — bez child_of apakšvaicājuma;
#         4. Optimizēta write() metode — selektīvs _fields_sync izsaukums;
#         5. PostgreSQL pg_trgm GIN indeksi ILIKE meklēšanai.
#
#  EN: This file contains res.partner model optimization, adding four main
#      changes to the original Odoo 19.0 res_partner.py code in order to
#      improve system performance with large datasets (100 000+ records):
#
#         1. Field caching — store=True on contact_address and email_formatted;
#         2. Shortened _rec_names_search — from 5 to 2 indexed fields;
#         3. Rewritten _search_display_name — without child_of subquery;
#         4. Optimized write() method — selective _fields_sync invocation;
#         5. PostgreSQL pg_trgm GIN indexes for ILIKE search.
#
#  LV: Modulis tiek instalēts kā paplašinājums (_inherit = 'res.partner'),
#      neveicot tiešas izmaiņas Odoo pamatkodā. Tas nodrošina saderību ar
#      turpmākajiem Odoo atjauninājumiem.
#
#  EN: The module is installed as an extension (_inherit = 'res.partner')
#      without modifying the Odoo core code directly. This ensures
#      compatibility with future Odoo updates.
# ============================================================================

from __future__ import annotations

# LV: Standarta Python bibliotēkas — izmantotas _fields_sync un set operācijām
# EN: Standard Python libraries — used for _fields_sync and set operations
from collections import defaultdict

# LV: Odoo iebūvētie API rīki — ORM, lauku definīcijas, modeļu mantošana
# EN: Built-in Odoo API tools — ORM, field definitions, model inheritance
from odoo import api, fields, models, tools


class ResPartner(models.Model):
    """
    LV: res.partner modeļa paplašinājums ar veiktspējas optimizācijām.
        Mantošanas mehānisms (_inherit) ļauj pievienot izmaiņas, neaizstājot
        oriģinālo modeli — tas nodrošina, ka visi citi Odoo moduļi (sale,
        purchase, account, crm) turpina darboties bez modifikācijām.

    EN: res.partner model extension with performance optimizations.
        The inheritance mechanism (_inherit) allows adding changes without
        replacing the original model — this ensures that all other Odoo
        modules (sale, purchase, account, crm) continue to work without
        modifications.
    """
    _inherit = 'res.partner'

    # ========================================================================
    # 1. IZMAIŅAS / CHANGE 1: _rec_names_search saraksta saīsinājums
    # ========================================================================
    #
    # LV: ORIĢINĀLS (Odoo 19.0 res_partner.py, 189. rinda):
    #     _rec_names_search = ['complete_name', 'email', 'ref', 'vat',
    #                          'company_registry']
    #
    #     PROBLĒMA: Ikviens meklēšanas pieprasījums ģenerē SQL vaicājumu ar
    #     5 OR ILIKE klauzulām. Pie 100 000 ierakstu un 50 vienlaicīgiem
    #     lietotājiem tas rada 4248 ms latenci (skatīt 4.4.2. apakšnodaļu).
    #
    #     RISINĀJUMS: Atstājam tikai 2 visbiežāk izmantotos laukus, kuri
    #     papildus tiks indeksēti ar pg_trgm trigrammu indeksiem (skatīt
    #     šī faila beigās init() metodi).
    #
    # EN: ORIGINAL (Odoo 19.0 res_partner.py, line 189):
    #     _rec_names_search = ['complete_name', 'email', 'ref', 'vat',
    #                          'company_registry']
    #
    #     PROBLEM: Every search request generates an SQL query with 5 OR
    #     ILIKE clauses. With 100 000 records and 50 concurrent users this
    #     results in 4248 ms latency (see chapter 4.4.2).
    #
    #     SOLUTION: Keep only the 2 most frequently used fields, which will
    #     additionally be indexed with pg_trgm trigram indexes (see init()
    #     method at the end of this file).
    # ------------------------------------------------------------------------
    _rec_names_search = ['complete_name', 'email']

    # ========================================================================
    # 2. IZMAIŅAS / CHANGE 2: contact_address lauks ar kešdarbi
    # ========================================================================
    #
    # LV: ORIĢINĀLS (Odoo 19.0 res_partner.py, 299. rinda):
    #     contact_address = fields.Char(
    #         compute='_compute_contact_address',
    #         string='Complete Address')
    #
    #     PROBLĒMA: Bez store=True vērtība tiek pārrēķināta KATRU REIZI, kad
    #     to pieprasa. Ielādējot 1000 partneru sarakstu, _compute_contact_
    #     address() tiek izsaukta 1000 reižu, katru reizi piekļūstot country_id
    #     un state_id saistītajām tabulām. Tas rada N+1 vaicājumu problēmu.
    #
    #     RISINĀJUMS:
    #       - store=True       — saglabā vērtību datubāzē kā parastu kolonnu;
    #       - index='btree_not_null' — daļējs B-koka indekss, kas izlaiž NULL
    #                            vērtības (taupa diska vietu un paātrina
    #                            filtrēšanu pa adresi).
    #
    #     Vērtība tiks pārrēķināta tikai tad, kad mainīsies kāds no
    #     @api.depends laukiem (street, city, country_id u.c.).
    #
    # EN: ORIGINAL (Odoo 19.0 res_partner.py, line 299):
    #     contact_address = fields.Char(
    #         compute='_compute_contact_address',
    #         string='Complete Address')
    #
    #     PROBLEM: Without store=True the value is recalculated EVERY TIME
    #     it is requested. When loading a list of 1000 partners,
    #     _compute_contact_address() is invoked 1000 times, each time
    #     accessing country_id and state_id related tables. This causes
    #     the N+1 query problem.
    #
    #     SOLUTION:
    #       - store=True       — stores the value in the database as a
    #                            regular column;
    #       - index='btree_not_null' — partial B-tree index that skips NULL
    #                            values (saves disk space and speeds up
    #                            filtering by address).
    #
    #     The value will be recalculated only when one of the @api.depends
    #     fields changes (street, city, country_id, etc.).
    # ------------------------------------------------------------------------
    contact_address = fields.Char(
        compute='_compute_contact_address',
        string='Complete Address',
        store=True,                    # LV: kešo DB / EN: cache in DB
        index='btree_not_null',        # LV: daļējs indekss / EN: partial index
    )

    # ========================================================================
    # 3. IZMAIŅAS / CHANGE 3: email_formatted lauks ar kešdarbi
    # ========================================================================
    #
    # LV: ORIĢINĀLS (Odoo 19.0 res_partner.py, 273.-275. rinda):
    #     email_formatted = fields.Char(
    #         'Formatted Email', compute='_compute_email_formatted',
    #         help='Format email address "Name <email@domain>"')
    #
    #     PROBLĒMA: Tāpat kā contact_address — vērtība netiek kešota, un tiek
    #     pārrēķināta katrā saraksta ielādes reizē. Lai gan _compute_email_
    #     formatted() ir vienkāršāks par contact_address, tas joprojām rada
    #     papildu CPU slodzi pie liela ierakstu skaita.
    #
    #     RISINĀJUMS: Pievienojam store=True, lai vērtība tiktu saglabāta
    #     datubāzē. Indekss šeit nav nepieciešams, jo email_formatted nav
    #     paredzēts meklēšanai (tas ir tikai attēlošanas formāts).
    #
    # EN: ORIGINAL (Odoo 19.0 res_partner.py, lines 273-275):
    #     email_formatted = fields.Char(
    #         'Formatted Email', compute='_compute_email_formatted',
    #         help='Format email address "Name <email@domain>"')
    #
    #     PROBLEM: Same as contact_address — the value is not cached and is
    #     recalculated on every list load. Although _compute_email_formatted()
    #     is simpler than contact_address, it still creates additional CPU
    #     load with a large number of records.
    #
    #     SOLUTION: Add store=True so the value is saved in the database.
    #     An index is not necessary here because email_formatted is not
    #     intended for searching (it is only a display format).
    # ------------------------------------------------------------------------
    email_formatted = fields.Char(
        'Formatted Email',
        compute='_compute_email_formatted',
        store=True,                    # LV: kešo DB / EN: cache in DB
        help='Format email address "Name <email@domain>"',
    )

    # ========================================================================
    # 4. IZMAIŅAS / CHANGE 4: _search_display_name() metodes pārrakstīšana
    # ========================================================================
    #
    # LV: ORIĢINĀLS (Odoo 19.0 res_partner.py, 174.-181. rinda):
    #     @api.model
    #     def _search_display_name(self, operator, value):
    #         domain = super()._search_display_name(operator, value)
    #         if operator.endswith('like'):
    #             if operator.startswith('not'):
    #                 return NotImplemented
    #             return [('id', 'child_of', tuple(self._search(domain)))]
    #         return domain
    #
    #     PROBLĒMA: Oriģinālā metode izmanto child_of apakšvaicājumu, kas:
    #       a) ielādē visus pakārtotos partnerus (child_ids) — papildu Seq Scan;
    #       b) palaiž self._search(domain) atsevišķi — vēl viens vaicājums;
    #       c) ar tuple(...) materializē rezultātu atmiņā — palielina RAM
    #          patēriņu.
    #
    #     RISINĀJUMS: Atgriežam tiešu OR domain ar diviem nosacījumiem
    #     (complete_name, email), izvairoties no child_of un papildu _search()
    #     izsaukuma. Citiem operatoriem (=, !=, in) saglabājam super()
    #     uzvedību, lai netiktu zaudēta saderība ar Odoo iebūvētajiem
    #     mehānismiem (piem., domēnu validācija formās).
    #
    # EN: ORIGINAL (Odoo 19.0 res_partner.py, lines 174-181):
    #     @api.model
    #     def _search_display_name(self, operator, value):
    #         domain = super()._search_display_name(operator, value)
    #         if operator.endswith('like'):
    #             if operator.startswith('not'):
    #                 return NotImplemented
    #             return [('id', 'child_of', tuple(self._search(domain)))]
    #         return domain
    #
    #     PROBLEM: The original method uses a child_of subquery, which:
    #       a) loads all child partners (child_ids) — extra Seq Scan;
    #       b) runs self._search(domain) separately — another query;
    #       c) materializes the result in memory with tuple(...) — increases
    #          RAM consumption.
    #
    #     SOLUTION: Return a direct OR domain with two conditions
    #     (complete_name, email), avoiding child_of and the additional
    #     _search() call. For other operators (=, !=, in) we keep super()
    #     behaviour so that compatibility with built-in Odoo mechanisms
    #     (e.g. domain validation in forms) is not lost.
    # ------------------------------------------------------------------------
    @api.model
    def _search_display_name(self, operator, value):
        # LV: Apstrādājam tikai ILIKE/LIKE meklēšanu — pārējiem operatoriem
        #     atstājam standarta Odoo uzvedību.
        # EN: Handle only ILIKE/LIKE search — for other operators we leave
        #     the standard Odoo behaviour.
        if operator in ('ilike', 'like') and value:
            # LV: Tiešs OR domain bez child_of apakšvaicājuma.
            #     '|' Polish-prefix notācijā nozīmē "vai" starp diviem
            #     nākamajiem nosacījumiem.
            # EN: Direct OR domain without child_of subquery.
            #     '|' in Polish-prefix notation means "or" between the next
            #     two conditions.
            return [
                '|',
                ('complete_name', operator, value),
                ('email', operator, value),
            ]

        # LV: Citiem operatoriem (=, !=, in, not in u.c.) izmantojam
        #     standarta Odoo loģiku — saglabājam pilnu saderību.
        # EN: For other operators (=, !=, in, not in, etc.) we use the
        #     standard Odoo logic — preserving full compatibility.
        return super()._search_display_name(operator, value)

    # ========================================================================
    # 5. IZMAIŅAS / CHANGE 5: write() metodes optimizācija pret N+1 problēmu
    # ========================================================================
    #
    # LV: ORIĢINĀLS (Odoo 19.0 res_partner.py, 842.-910. rinda, saīsināts):
    #     def write(self, vals):
    #         # ... validācijas ...
    #         pre_values_list = [{fname: partner[fname] for fname in vals}
    #                            for partner in self]
    #         result = result and super().write(vals)
    #         for partner, pre_values in zip(self, pre_values_list):
    #             updated = {fname: fvalue for fname, fvalue in vals.items()
    #                        if partner[fname] != pre_values.get(fname)}
    #             if updated:
    #                 partner._fields_sync(updated)   # <-- N+1 risks
    #         return result
    #
    #     PROBLĒMA: Cikla iekšienē katram partnerim atsevišķi tiek izsaukts
    #     _fields_sync(), kas savukārt iniciē adreses un komerciālo lauku
    #     sinhronizāciju ar child_ids un parent_id. Pie 500 partneru masveida
    #     atjaunināšanas tas var radīt 500+ papildu DB vaicājumus — klasisku
    #     N+1 vaicājumu problēmu.
    #
    #     Vissliktāk: _fields_sync tiek izsaukts pat tad, ja vals satur tikai
    #     tādus laukus, kas nav saistīti ar adresi (piem., color, comment).
    #
    #     RISINĀJUMS: Pirms super().write() pārbaudām, vai vals reāli satur
    #     adreses vai komerciālos laukus. Ja nē — izlaižam _fields_sync ciklu
    #     pilnībā, izmantojot konteksta karodziņu _partners_skip_fields_sync,
    #     ko jau atbalsta oriģinālā Odoo create() metode (skatīt res_partner.py
    #     928. rindu).
    #
    # EN: ORIGINAL (Odoo 19.0 res_partner.py, lines 842-910, abbreviated):
    #     def write(self, vals):
    #         # ... validations ...
    #         pre_values_list = [{fname: partner[fname] for fname in vals}
    #                            for partner in self]
    #         result = result and super().write(vals)
    #         for partner, pre_values in zip(self, pre_values_list):
    #             updated = {fname: fvalue for fname, fvalue in vals.items()
    #                        if partner[fname] != pre_values.get(fname)}
    #             if updated:
    #                 partner._fields_sync(updated)   # <-- N+1 risk
    #         return result
    #
    #     PROBLEM: Inside the loop _fields_sync() is invoked separately for
    #     each partner, which in turn initiates synchronization of address
    #     and commercial fields with child_ids and parent_id. With a mass
    #     update of 500 partners this can cause 500+ extra DB queries — the
    #     classic N+1 query problem.
    #
    #     Worst of all: _fields_sync is called even if vals contains only
    #     fields unrelated to addresses (e.g., color, comment).
    #
    #     SOLUTION: Before super().write() we check whether vals actually
    #     contains address or commercial fields. If not — we skip the entire
    #     _fields_sync loop using the _partners_skip_fields_sync context flag
    #     already supported by the original Odoo create() method (see
    #     res_partner.py line 928).
    # ------------------------------------------------------------------------
    def write(self, vals):
        # LV: Iegūstam sinhronizējamo lauku kopu — adreses lauki + komerciālie
        #     lauki + vecāka maiņa (parent_id). Konvertējam uz set, lai
        #     krustošanās pārbaude (&) būtu O(1).
        # EN: Obtain the set of synchronizable fields — address fields +
        #     commercial fields + parent change (parent_id). Convert to set
        #     so that intersection check (&) is O(1).
        sync_triggers = (
            set(self._address_fields())
            | set(self._synced_commercial_fields())
            | {'parent_id'}
        )

        # LV: Pārbaudām, vai vals satur kaut vienu sinhronizējamo lauku.
        #     Ja vals atslēgu kopa nepārklājas ar sync_triggers, tad _fields_
        #     sync nav vajadzīgs un to var droši izlaist.
        # EN: Check whether vals contains at least one synchronizable field.
        #     If the vals key set does not intersect with sync_triggers,
        #     then _fields_sync is not needed and can be safely skipped.
        if not (sync_triggers & set(vals.keys())):
            # LV: Izsaucam super().write() ar kontekstu, kas signalizē
            #     pakārtotajiem moduļiem nepalaist _fields_sync. Šis
            #     karodziņš jau eksistē Odoo iekšienē (res_partner.py 928.r.).
            # EN: Call super().write() with a context that signals
            #     downstream modules to skip _fields_sync. This flag already
            #     exists inside Odoo (res_partner.py line 928).
            return super(
                ResPartner,
                self.with_context(_partners_skip_fields_sync=True),
            ).write(vals)

        # LV: Ja vals satur sinhronizējamus laukus — izpildām pilnu
        #     oriģinālo loģiku, lai netiktu zaudēta datu integritāte starp
        #     vecāka un bērna partneriem.
        # EN: If vals contains synchronizable fields — execute the full
        #     original logic, so that data integrity between parent and
        #     child partners is not lost.
        return super().write(vals)

    # ========================================================================
    # 6. IZMAIŅAS / CHANGE 6: PostgreSQL trigrammu indeksi ILIKE meklēšanai
    # ========================================================================
    #
    # LV: PROBLĒMA: PostgreSQL standarta B-koka indekss neatbalsta
    #     ILIKE '%vērtība%' šablonu, jo wildcard simboli abās pusēs neļauj
    #     izmantot indeksa hierarhiju. Tas ir galvenais iemesls, kāpēc
    #     standarta Odoo meklēšana lielos datos rada Seq Scan.
    #
    #     RISINĀJUMS: Izmantojam PostgreSQL pg_trgm paplašinājumu, kas
    #     sadala tekstu trīs simbolu fragmentos (trigrammās) un veido GIN
    #     (Generalized Inverted Index) indeksu. Šis indeksu tips atbalsta
    #     ILIKE meklēšanu un PostgreSQL spēj izmantot Bitmap Index Scan
    #     vietā Seq Scan.
    #
    #     init() metode tiek izsaukta automātiski moduļa instalēšanas vai
    #     atjaunināšanas laikā. CREATE EXTENSION un tools.create_index() ir
    #     idempotenti — atkārtota izsaukšana neradīs kļūdu.
    #
    # EN: PROBLEM: PostgreSQL standard B-tree index does not support the
    #     ILIKE '%value%' pattern, because wildcard symbols on both sides
    #     prevent using the index hierarchy. This is the main reason why
    #     standard Odoo search produces a Seq Scan on large data.
    #
    #     SOLUTION: We use the PostgreSQL pg_trgm extension, which splits
    #     text into three-character fragments (trigrams) and builds a GIN
    #     (Generalized Inverted Index) index. This index type supports
    #     ILIKE search and PostgreSQL is able to use Bitmap Index Scan
    #     instead of Seq Scan.
    #
    #     The init() method is called automatically during module
    #     installation or upgrade. CREATE EXTENSION and tools.create_index()
    #     are idempotent — repeated invocation will not raise an error.
    # ------------------------------------------------------------------------
def init(self):
        # LV: Izsaucam vecāka init(), lai netiktu pārrakstīta cita loģika,
        #     ko Odoo vai citi moduļi var būt definējuši.
        # EN: Call the parent init() so we do not overwrite any other
        #     logic that Odoo or other modules may have defined.
        super().init()

        # LV: 1. solis — aktivizējam pg_trgm paplašinājumu PostgreSQL līmenī.
        #     IF NOT EXISTS klauzula nodrošina, ka komanda ir droša pat ja
        #     paplašinājums jau ir aktivizēts.
        # EN: Step 1 — activate the pg_trgm extension at PostgreSQL level.
        #     The IF NOT EXISTS clause ensures the command is safe even
        #     if the extension is already active.
        self.env.cr.execute(
            "CREATE EXTENSION IF NOT EXISTS pg_trgm"
        )

        # LV: 2. solis — GIN trigrammu indekss complete_name laukam.
        #     Izmantojam tiešu SQL CREATE INDEX IF NOT EXISTS vietā
        #     tools.create_index(), jo Odoo 19 tools.create_index() ar
        #     method='gin' un gin_trgm_ops operatoru klasi neizveido
        #     indeksu pareizi. Tiešais SQL nodrošina identisks rezultāts
        #     un IF NOT EXISTS garantē idempotentumu — atkārtota izpilde
        #     (piemēram, moduļa upgrade laikā) neradīs kļūdu.
        # EN: Step 2 — GIN trigram index for the complete_name field.
        #     We use direct SQL CREATE INDEX IF NOT EXISTS instead of
        #     tools.create_index(), because in Odoo 19 tools.create_index()
        #     with method='gin' and gin_trgm_ops operator class does not
        #     create the index correctly. Direct SQL ensures the same result
        #     and IF NOT EXISTS guarantees idempotency — repeated execution
        #     (e.g. during module upgrade) will not raise an error.
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS res_partner_complete_name_trgm_idx
            ON res_partner
            USING gin (complete_name gin_trgm_ops)
        """)

        # LV: 3. solis — GIN trigrammu indekss email laukam.
        #     Tā kā _rec_names_search satur tikai complete_name un email,
        #     pietiek ar šiem diviem indeksiem, lai pārklātu visus meklēšanas
        #     scenārijus, kas iet caur _search_display_name.
        # EN: Step 3 — GIN trigram index for the email field.
        #     Since _rec_names_search contains only complete_name and email,
        #     these two indexes are sufficient to cover all search scenarios
        #     that go through _search_display_name.
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS res_partner_email_trgm_idx
            ON res_partner
            USING gin (email gin_trgm_ops)
        """)

# ============================================================================
#  KOPSAVILKUMS / SUMMARY
# ============================================================================
#
#  LV: Šī faila kopējais izmaiņu apjoms salīdzinājumā ar oriģinālo Odoo
#      res_partner.py kodu:
#
#         Izmaiņa                                    Rindas oriģ. failā
#         ─────────────────────────────────────────  ──────────────────
#         1. _rec_names_search saīsinājums           189
#         2. contact_address ar store=True           299
#         3. email_formatted ar store=True           273-275
#         4. _search_display_name pārrakstīšana      174-181
#         5. write() ar selektīvu _fields_sync       842-910
#         6. PostgreSQL pg_trgm GIN indeksi          (jauna funkcionalitāte)
#
#      Visas izmaiņas ir veiktas paplašinājuma modulī ar _inherit, neveicot
#      tiešas modifikācijas Odoo pamatkodā. Tas garantē saderību ar
#      turpmākajiem Odoo atjauninājumiem.
#
#  EN: Total scope of changes in this file compared to the original Odoo
#      res_partner.py code:
#
#         Change                                     Original file lines
#         ─────────────────────────────────────────  ──────────────────
#         1. _rec_names_search shortening            189
#         2. contact_address with store=True         299
#         3. email_formatted with store=True         273-275
#         4. _search_display_name rewrite            174-181
#         5. write() with selective _fields_sync     842-910
#         6. PostgreSQL pg_trgm GIN indexes          (new functionality)
#
#      All changes are made in an extension module with _inherit, without
#      modifying the Odoo core code directly. This guarantees compatibility
#      with future Odoo updates.
# ============================================================================
