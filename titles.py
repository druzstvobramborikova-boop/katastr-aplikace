# -*- coding: utf-8 -*-
"""
titles.py
Databáze titulů, které aplikace umí rozpoznat a oddělit od jména.

Sem přidávejte nové tituly, pokud narazíte na PDF, kde se nějaký
titul nerozpoznal správně - stačí ho přidat do příslušné kategorie
níže, nic dalšího upravovat nemusíte.

Jak to funguje: aplikace hledá tyto řetězce KDEKOLIV ve jméně
(nezávisle na velikosti písmen) a odstraní je - zbytek je jméno a
příjmení. Tituly se hledají od nejdelších po nejkratší, aby se
předešlo částečným shodám (např. aby se "MUDr." nerozpadlo na
"MU" + "Dr.").
"""

# Tituly PŘED jménem (bakalářské, magisterské, doktorské) --------------------
TITLES_PRED_JMENEM = [
    'Bc.', 'BcA.',
    'Ing.', 'Ing. arch.', 'arch.',
    'MUDr.', 'MDDr.', 'MVDr.',
    'JUDr.',
    'PhDr.', 'RNDr.', 'PharmDr.', 'PaedDr.', 'ThDr.', 'ThLic.',
    'RSDr.',
    'Mgr.', 'MgA.',
    'Doc.',
    'Prof.',
    'akad. mal.', 'akad. soch.', 'ak. mal.', 'ak. arch.',
]

# Vědecké a jiné hodnosti ZA jménem ------------------------------------------
# (Ph.D. má víc běžně používaných zápisů, proto je uvedeno několikrát)
TITLES_ZA_JMENEM = [
    'Ph.D.', 'Ph.D', 'PhD.', 'PhD', 'Phd.',
    'Th.D.', 'Th.D',
    'CSc.', 'DrSc.', 'DSc.',
    'DiS.',
    'MBA', 'MPA', 'LL.M.',
    'M.A.', 'M.Sc.', 'B.A.', 'B.Sc.',
]

# Kompletní seznam pro vyhledávání (pořadí zde není podstatné - v kódu
# se řadí podle délky, aby se odstranily nejdřív delší tvary)
TITLE_LIST = TITLES_PRED_JMENEM + TITLES_ZA_JMENEM
