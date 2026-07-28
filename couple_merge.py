# -*- coding: utf-8 -*-
"""
couple_merge.py
Rozpozná v tabulce vlastníků manželské páry (stejná adresa, opačné
pohlaví, shodný kořen příjmení - včetně tvarů jako Novák/Nováková,
Novotný/Novotná, Svoboda/Svobodová) a označí je, aby šlo pro hromadnou
korespondenci poslat jen jeden dopis na pár.

Přidává do tabulky dva sloupce:
- "Pár (manželé)": ANO/NE
- "Odeslat dopis": ANO / "NE (viz manžel/manželka výše)"
"""

import pandas as pd


def canonical_surname_root(surname: str) -> str:
    """
    Vrátí 'kořen' příjmení pro porovnání mužského a ženského tvaru.
    Zvládá běžné vzory:
    - Novák / Nováková  -> "novák"
    - Novotný / Novotná -> "novotn"
    - Svoboda / Svobodová -> "svobod"
    """
    s = (surname or '').strip().lower()
    if not s:
        return ''
    if s.endswith('ová'):
        return s[:-3]
    if s.endswith('ý'):
        return s[:-1]
    if s.endswith('á'):
        return s[:-1]
    if s.endswith('a'):
        return s[:-1]
    return s


def gender_from_osloveni(osloveni: str):
    """Odvodí pohlaví z připraveného sloupce Oslovení. Vrátí 'M', 'F',
    nebo None (nejednoznačné / firma)."""
    osloveni = (osloveni or '').strip()
    if osloveni.startswith('Vážená paní'):
        return 'F'
    if osloveni.startswith('Vážený pane') and not osloveni.startswith('Vážený pane / Vážená paní'):
        return 'M'
    return None


def pluralize_surname(surname: str) -> str:
    """
    Vrátí příjmení v množném čísle pro použití s "manželé", např.:
    - Novák -> Novákovi
    - Novotný -> Novotní
    - Svoboda -> Svobodovi
    Jde o heuristiku - u neobvyklých příjmení nemusí být tvar přesný,
    proto se řádek, kde se použije, vždy označí ke kontrole.
    """
    s = (surname or '').strip()
    if not s:
        return s
    low = s.lower()
    if low.endswith('ský'):
        return s[:-3] + 'ští'
    if low.endswith('cký'):
        return s[:-3] + 'čtí'
    if low.endswith('ký'):
        return s[:-2] + 'cí'
    if low.endswith('ý'):
        return s[:-1] + 'í'
    if low.endswith('a'):
        return s[:-1] + 'ovi'
    return s + 'ovi'


def _build_group_key(df, address_cols, unit_col=None, file_col=None):
    """
    Sestaví klíč pro seskupení řádků patřících k jedné nemovitosti/
    jednotce. Kombinuje ADRESU (vždy) s číslem jednotky (pokud je
    k dispozici) - u některých typů PDF sdílí stejnou adresu budovy
    všichni vlastníci v domě, takže samotná adresa k rozlišení
    jednotlivých bytů nestačí; číslo jednotky (je-li známé) ji dál
    zpřesní. Když číslo jednotky chybí (prázdné u obou), spoléhá se
    jen na adresu jako dřív.
    """
    group_key = df[address_cols].astype(str).agg('|'.join, axis=1)
    if unit_col and unit_col in df.columns:
        group_key = df[unit_col].astype(str) + '||' + group_key
    if file_col and file_col in df.columns:
        group_key = df[file_col].astype(str) + '||' + group_key
    return group_key


def build_combined_sjm_rows(df, jmeno_col, prijmeni_col, osloveni_col,
                             address_cols, sjm_flag_col, unit_col=None,
                             file_col=None):
    """
    Pro dvojice řádků, které:
    - obě pocházejí ze zápisu SJ (společné jmění manželů) v PDF
      (sjm_flag_col == True u obou),
    - mají shodný kořen příjmení,
    - mají shodnou adresu,
    - patří ke stejné nemovitosti/jednotce (unit_col, pokud je k dispozici)
      nebo stejnému zdrojovému souboru,

    vloží ZA tuto dvojici nový řádek se společným oslovením
    ("Vážení manželé Novákovi"), společným jménem ("Radka a Jiří") a
    příjmením v množném čísle ("Novákovi"). Původní dva řádky zůstávají.

    Vrací (nový_df, seznam_indexů_k_zvýraznění) - indexy odpovídají
    řádkům v NOVÉM (vráceném) dataframu, které mají být vizuálně
    odlišené (2 původní + 1 nově vytvořený).
    """
    df = df.reset_index(drop=True).copy()
    if sjm_flag_col not in df.columns:
        return df, []

    group_key = _build_group_key(df, address_cols, unit_col, file_col)

    insert_after = {}
    highlight_positions = set()

    for _, idx in df.groupby(group_key).groups.items():
        idx = list(idx)
        if len(idx) != 2:
            continue
        i1, i2 = idx
        r1, r2 = df.loc[i1], df.loc[i2]

        if not (bool(r1[sjm_flag_col]) and bool(r2[sjm_flag_col])):
            continue

        root1 = canonical_surname_root(r1[prijmeni_col])
        root2 = canonical_surname_root(r2[prijmeni_col])
        if not root1 or root1 != root2:
            continue

        addr1 = tuple(str(r1[c]).strip().lower() for c in address_cols)
        addr2 = tuple(str(r2[c]).strip().lower() for c in address_cols)
        if any(a == '' for a in addr1) or addr1 != addr2:
            continue

        g1 = gender_from_osloveni(r1[osloveni_col])
        g2 = gender_from_osloveni(r2[osloveni_col])

        if g1 == 'F' and g2 == 'M':
            female_row, male_row = r1, r2
        elif g2 == 'F' and g1 == 'M':
            female_row, male_row = r2, r1
        else:
            female_row, male_row = r1, r2

        female_first = str(female_row[jmeno_col]).split()[0] if str(female_row[jmeno_col]).strip() else ''
        male_first = str(male_row[jmeno_col]).split()[0] if str(male_row[jmeno_col]).strip() else ''
        combined_jmeno = ' a '.join(p for p in [female_first, male_first] if p)

        plural_surname = pluralize_surname(male_row[prijmeni_col] or female_row[prijmeni_col])

        combined = {c: male_row[c] for c in df.columns}
        combined[jmeno_col] = combined_jmeno
        combined[prijmeni_col] = plural_surname
        combined[osloveni_col] = f'Vážení manželé {plural_surname}'
        if 'Titul' in df.columns:
            combined['Titul'] = ''
        combined['Poznámka'] = (
            'Automaticky vytvořený společný řádek pro manžele (SJ) - '
            'zkontrolujte oslovení a příjmení v množném čísle'
        )
        combined['Kontrola'] = 'ANO' if g1 not in ('F', 'M') or g2 not in ('F', 'M') else 'NE'
        if 'Pár (manželé)' in df.columns:
            combined['Pár (manželé)'] = 'ANO'
        if 'Odeslat dopis' in df.columns:
            combined['Odeslat dopis'] = 'ANO'
            df.loc[i1, 'Odeslat dopis'] = 'NE (viz spojený řádek níže)'
            df.loc[i2, 'Odeslat dopis'] = 'NE (viz spojený řádek níže)'

        insert_after[max(idx)] = combined
        highlight_positions.update(idx)

    records = df.to_dict('records')
    new_records = []
    new_highlight_indices = []
    for pos, rec in enumerate(records):
        new_records.append(rec)
        if pos in highlight_positions:
            new_highlight_indices.append(len(new_records) - 1)
        if pos in insert_after:
            new_records.append(insert_after[pos])
            new_highlight_indices.append(len(new_records) - 1)

    new_df = pd.DataFrame(new_records, columns=df.columns)
    return new_df, new_highlight_indices


def mark_married_couples(df, prijmeni_col, osloveni_col, address_cols, unit_col=None, file_col=None):
    """
    Vrátí kopii df se dvěma novými sloupci: "Pár (manželé)" a
    "Odeslat dopis".

    - prijmeni_col: název sloupce s příjmením
    - osloveni_col: název sloupce s hotovým oslovením (pro odvození pohlaví)
    - address_cols: seznam sloupců, které společně tvoří adresu
      (použije se jako bezpečnostní pojistka, že jde opravdu o stejnou adresu)
    - unit_col: pokud tabulka obsahuje sloupec s číslem bytové jednotky,
      použije se jako primární seskupovací klíč (přesnější než adresa)
    - file_col: pokud je zadán (např. při zpracování více PDF najednou),
      páry se nikdy nehledají NAPŘÍČ různými zdrojovými soubory
    """
    df = df.copy()
    df['Pár (manželé)'] = 'NE'
    df['Odeslat dopis'] = 'ANO'

    group_key = _build_group_key(df, address_cols, unit_col, file_col)

    for _, idx in df.groupby(group_key).groups.items():
        idx = list(idx)
        if len(idx) != 2:
            continue
        i1, i2 = idx
        r1, r2 = df.loc[i1], df.loc[i2]

        g1 = gender_from_osloveni(r1[osloveni_col])
        g2 = gender_from_osloveni(r2[osloveni_col])
        if g1 is None or g2 is None or g1 == g2:
            continue

        root1 = canonical_surname_root(r1[prijmeni_col])
        root2 = canonical_surname_root(r2[prijmeni_col])
        if not root1 or root1 != root2:
            continue

        addr1 = tuple(str(r1[c]).strip().lower() for c in address_cols)
        addr2 = tuple(str(r2[c]).strip().lower() for c in address_cols)
        if any(a == '' for a in addr1) or addr1 != addr2:
            continue

        df.loc[i1, 'Pár (manželé)'] = 'ANO'
        df.loc[i2, 'Pár (manželé)'] = 'ANO'
        df.loc[i2, 'Odeslat dopis'] = 'NE (viz manžel/manželka výše)'

    return df
