# -*- coding: utf-8 -*-
# ============================================================================
# LV: Bakalaura darba paplašinājuma moduļa manifests
# EN: Bachelor thesis extension module manifest
# ============================================================================
# Autors / Author: Maksims Koļcovs (231RDB363)
# Zinātniskais vadītājs / Supervisor: Mg.sc.ing. Valdis Saulespurēns
# Rīgas Tehniskā Universitāte, 2026
# ============================================================================

{
    'name': 'Custom Partner Optimization',
    'version': '19.0.1.0.0',
    'category': 'Customizations',
    'summary': 'res.partner model performance optimization for large datasets',
    'description': """
        LV: Šis modulis optimizē res.partner modeļa veiktspēju lielos datu apjomos.
        Tiek risinātas trīs galvenās veiktspējas problēmas, kas identificētas
        bakalaura darbā:
            1) ILIKE meklēšanas neefektivitāte uz 5 laukiem;
            2) compute lauku contact_address un email_formatted nekešdarbe;
            3) N+1 vaicājumu problēma write() metodē.

        EN: This module optimizes res.partner model performance for large datasets.
        It addresses three main performance issues identified in the bachelor thesis:
            1) Inefficient ILIKE search on 5 fields;
            2) Non-cached compute fields contact_address and email_formatted;
            3) N+1 query problem in write() method.
    """,
    'author': 'Maksims Koļcovs',
    'website': 'https://github.com/Maksims-Kolcovs/baklaura_darbs_odoo',
    'depends': ['base'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
