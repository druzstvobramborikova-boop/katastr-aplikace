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

    if unit_col and unit_col in df.columns:
        group_key = df[unit_col].astype(str)
    else:
        group_key = df[address_cols].astype(str).agg('|'.join, axis=1)

    if file_col and file_col in df.columns:
        group_key = df[file_col].astype(str) + '||' + group_key

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
