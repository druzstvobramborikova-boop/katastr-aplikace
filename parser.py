# -*- coding: utf-8 -*-
"""
parser.py
Logika pro extrakci sekce "Vlastníci, jiní oprávnění" z PDF výpisu
z Nahlížení do katastru nemovitostí a její rozparsování do řádků
vhodných pro hromadnou korespondenci.

POZNÁMKA K SPOLEHLIVOSTI:
Formát PDF z Nahlížení do katastru se může mírně lišit podle typu
výpisu (LV, informace o stavbě, informace o pozemku) a podle toho, jak
pdfplumber text z PDF přečte. Parser proto pracuje s heuristikami
popsanými v komentářích. Pokud parser u konkrétního PDF něco rozpozná
špatně, nejprve se podívejte do "debug" náhledu extrahovaného textu
v aplikaci - podle něj lze snadno doladit regulární výrazy níže.
"""

import re
import pdfplumber

try:
    from vokativ import vokativ as _vokativ_lib
except ImportError:  # knihovna nemusí být při lokálním testování nainstalovaná
    _vokativ_lib = None

from couple_merge import canonical_surname_root
from titles import TITLE_LIST


def vocative_surname(prijmeni: str, is_woman):
    """
    Vrátí příjmení vyskloňované do 5. pádu (vokativu) pomocí knihovny
    `vokativ` (https://pypi.org/project/vokativ/). Pokud knihovna není
    dostupná, jméno nelze sklonit, nebo dojde k chybě, vrátí (původní
    příjmení beze změny, False) - druhá hodnota říká, jestli se
    skloňování povedlo.
    `is_woman`: True/False pokud známe pohlaví, None pro automatickou
    detekci knihovnou (méně spolehlivé).
    """
    prijmeni = (prijmeni or '').strip()
    if not prijmeni or _vokativ_lib is None:
        return prijmeni, False
    try:
        kwargs = {'last_name': True}
        if is_woman is not None:
            kwargs['woman'] = is_woman
        result = _vokativ_lib(prijmeni, **kwargs)
        if not result:
            return prijmeni, False
        result = result[0].upper() + result[1:] if len(result) > 1 else result.upper()
        return result, True
    except Exception:
        return prijmeni, False


# ---------------------------------------------------------------------------
# Konstanty / slovníky
# ---------------------------------------------------------------------------

COLUMNS = [
    'Oslovení', 'Titul', 'Jméno', 'Příjmení / Název',
    'Ulice', 'Číslo domu', 'PSČ', 'Obec',
    'Kontrola', 'Poznámka', 'Původní adresa',
]

COMPANY_KEYWORDS = [
    's.r.o', 'a.s.', 'k.s.', 'v.o.s', 'spol. s r', 'družstvo',
    'státní podnik', 's.p.', 'česká republika', 'spolek', 'nadace',
    'nadační fond', 'fond', 'církev', 'farnost', 'diecéze', 'obec',
    'město', 'statutární město', 'kraj', 'společenství vlastníků',
    'úřad', 'ministerstvo', 'organizační složka', 'příspěvková organizace',
    'ústav', 'akciová společnost', 'svaz', 'svazek obcí', 'sdružení',
    'gmbh', 'ltd', 'inc.', 'b.v.', 'sp. z o.o', 'kft', 's.a.', 'plc', 'ooo',
]
COMPANY_KEYWORD_PATTERNS = [
    re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
    for kw in COMPANY_KEYWORDS
]

AMBIGUOUS_NAMES = {'nikola', 'saša', 'mája'}
MALE_NAMES_ENDING_A = {'jura', 'pepa', 'honza'}

JOINT_OWNERSHIP_PREFIXES = r'(?:SJM|SJ|BSM|MCP)'

NOISE_PATTERNS = [
    re.compile(r'^podíl\b', re.IGNORECASE),
    re.compile(r'^jednotka\b', re.IGNORECASE),
    re.compile(r'^nar\.', re.IGNORECASE),
    re.compile(r'^rč[:.]', re.IGNORECASE),
    re.compile(r'^r\.?\s*č\.?[:.]', re.IGNORECASE),
    re.compile(r'^datum narození', re.IGNORECASE),
    re.compile(r'^i[čc]o\b', re.IGNORECASE),
    re.compile(r'^typ vztahu', re.IGNORECASE),
    re.compile(r'^způsob ochrany', re.IGNORECASE),
    re.compile(r'^vlastnické právo\b', re.IGNORECASE),
    re.compile(r'^upozorn[ěe]n[ií]', re.IGNORECASE),
]

SECTION_START_PATTERNS = [
    r'Vlastníci,\s*jiní\s*oprávn[eě]n[ií]',
    r'Vlastník,\s*jiný\s*oprávněný',
]

SECTION_END_MARKERS = [
    'Příslušnost hospodařit s majetkem státu',
    'Způsob ochrany nemovitosti',
    'Vlastnictví jednotek',
    'Jiné zápisy', 'Omezení vlastnického práva', 'Cizí věcná práva',
    'Plomby', 'Řízení, v rámci', 'Věcná břemena', 'Zástavní právo',
    'Související zápisy',
]

FOOTER_LINE_PATTERNS = [
    re.compile(r'^Strana\s*\d+', re.IGNORECASE),
    re.compile(r'^Vyhotoveno', re.IGNORECASE),
    re.compile(r'^www\.cuzk\.cz', re.IGNORECASE),
    re.compile(r'^Nahlížení do katastru nemovitostí\s*$', re.IGNORECASE),
    re.compile(r'^Český úřad zeměměřický', re.IGNORECASE),
    re.compile(r'^https://nahlizenidokn', re.IGNORECASE),
    re.compile(r'^\d{2}\.\d{2}\.\d{2}\s+\d{2}:\d{2}\s+Informace', re.IGNORECASE),
    re.compile(r'^©\s*\d{4}', re.IGNORECASE),
]

PSC_RE = re.compile(r'(?<!\d)(\d{3}\s?\d{2})(?!\d)\s+(.+)$')


# ---------------------------------------------------------------------------
# Čtení PDF a extrakce sekce vlastníků
# ---------------------------------------------------------------------------

def _clean_full_text(full_text: str) -> str:
    lines = full_text.split('\n')
    out = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append('')
            continue
        if any(p.search(stripped) for p in FOOTER_LINE_PATTERNS):
            continue
        out.append(line)
    return '\n'.join(out)


def extract_full_text(file) -> str:
    chunks = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ''
            chunks.append(t)
    return _clean_full_text('\n'.join(chunks))


def extract_owners_section(full_text: str) -> str:
    start_match = None
    for pattern in SECTION_START_PATTERNS:
        m = re.search(pattern, full_text, re.IGNORECASE)
        if m:
            start_match = m
            break
    if start_match is None:
        return ''

    rest = full_text[start_match.end():]

    end_idx = len(rest)
    for marker in SECTION_END_MARKERS:
        idx = rest.find(marker)
        if idx != -1:
            end_idx = min(end_idx, idx)

    return rest[:end_idx].strip()


# ---------------------------------------------------------------------------
# Seskupení textu sekce na jednotlivé záznamy
# ---------------------------------------------------------------------------

def is_noise_line(line: str) -> bool:
    if any(p.search(line) for p in NOISE_PATTERNS):
        return True
    if not any(ch.isalpha() for ch in line):
        return True
    return False


JEDNOTKA_LINE_RE = re.compile(r'^jednotka\s*:\s*(.+)$', re.IGNORECASE)


def build_entries(section_text: str):
    """
    Vrací seznam slovníků {'text': ..., 'jednotka': ...}. 'jednotka' je
    číslo VLASTNÍ bytové jednotky daného vlastníka (první číslo za
    "Jednotka:" - další čísla v seznamu bývají společné části domu),
    nebo None, pokud se nepodařilo najít. Používá se jako doplňkový
    klíč pro spolehlivější rozpoznání manželů (viz couple_merge.py) -
    v tomto typu PDF totiž všichni vlastníci v domě sdílí stejnou
    adresu budovy, takže samotná adresa k rozlišení jednotek nestačí.
    """
    raw_lines = [l.strip() for l in section_text.split('\n')]
    raw_lines = [l for l in raw_lines if l]

    entries = []
    prev_was_content = False

    for line in raw_lines:
        jednotka_match = JEDNOTKA_LINE_RE.match(line)
        if jednotka_match and entries and entries[-1]['jednotka'] is None:
            entries[-1]['jednotka'] = jednotka_match.group(1).split(',')[0].strip()
            prev_was_content = False
            continue

        if is_noise_line(line):
            prev_was_content = False
            continue

        prev_ends_with_hyphen = bool(entries) and entries[-1]['text'].rstrip().endswith('-')

        if prev_was_content and entries and (',' not in line or prev_ends_with_hyphen):
            if prev_ends_with_hyphen:
                entries[-1]['text'] = entries[-1]['text'] + line
            else:
                entries[-1]['text'] = entries[-1]['text'] + ' ' + line
        else:
            entries.append({'text': line, 'jednotka': None})

        prev_was_content = True

    return entries


# ---------------------------------------------------------------------------
# Parsování adresy
# ---------------------------------------------------------------------------

def parse_address(raw: str) -> dict:
    original = raw.strip()
    kontrola = False
    notes = []

    if not original:
        return dict(ulice='', cislo_domu='', psc='', obec='',
                     kontrola=True, poznamka='Adresa chybí',
                     puvodni_adresa=original)

    parts = [p.strip() for p in original.split(',') if p.strip()]
    if not parts:
        return dict(ulice='', cislo_domu='', psc='', obec='',
                     kontrola=True, poznamka='Adresa chybí',
                     puvodni_adresa=original)

    psc = ''
    obec = ''
    last = parts[-1]
    m = PSC_RE.search(last)
    if m:
        psc_raw = re.sub(r'\s+', '', m.group(1))
        psc = psc_raw[:3] + ' ' + psc_raw[3:]
        obec = m.group(2).strip()
        parts = parts[:-1]
    else:
        if len(parts) >= 2:
            combined = parts[-2] + ' ' + parts[-1]
            m2 = PSC_RE.search(combined)
            if m2:
                psc_raw = re.sub(r'\s+', '', m2.group(1))
                psc = psc_raw[:3] + ' ' + psc_raw[3:]
                obec = m2.group(2).strip()
                parts = parts[:-2]
            else:
                obec = last
                parts = parts[:-1]
                kontrola = True
                notes.append('PSČ nerozpoznáno (možná zahraniční adresa)')
        else:
            obec = last
            parts = []
            kontrola = True
            notes.append('PSČ nerozpoznáno (možná zahraniční adresa)')

    ulice = ''
    cislo_domu = ''

    frac_match = re.search(r'\s+\d+\s*/\s*\d+\s*$', obec)
    if frac_match:
        obec = obec[:frac_match.start()].strip()
        notes.append('Odstraněn zlomek podílu omylem připojený k obci')

    if parts:
        street_part = parts[0]
        cp_match = re.match(r'^(č\.?\s?(p|ev)\.?\s?\d+\w*)$', street_part, re.IGNORECASE)
        if cp_match:
            cislo_domu = street_part
            ulice = obec  # adresa typu "č.p. 33" nemá ulici - použijeme název obce
        else:
            sm = re.match(r'^(.*\S)\s+(\d[\d/]*\w*)$', street_part)
            if sm:
                ulice = sm.group(1).strip()
                cislo_domu = sm.group(2).strip()
            else:
                ulice = street_part
                cislo_domu = ''
                kontrola = True
                notes.append('Číslo domu nerozpoznáno')

        if len(parts) > 1:
            district = ', '.join(parts[1:])
            notes.append(f'Možná část obce uvedená v adrese: "{district}"')
        elif not cp_match:
            kontrola = True
            street_display = f'{ulice} {cislo_domu}'.strip()
            notes.append(
                f'Nejisté, zda "{street_display}" je skutečná ulice, '
                'nebo jde o název obce/vesnice bez ulice - zkontrolujte'
            )
    else:
        if not obec:
            kontrola = True
            notes.append('Ulice / číslo domu nenalezeno')

    return dict(
        ulice=ulice, cislo_domu=cislo_domu, psc=psc, obec=obec,
        kontrola=kontrola, poznamka='; '.join(notes),
        puvodni_adresa=original,
    )


# ---------------------------------------------------------------------------
# Parsování jména a titulu
# ---------------------------------------------------------------------------

def extract_titles(text: str):
    found = []
    remaining = text
    for t in sorted(TITLE_LIST, key=len, reverse=True):
        pattern = re.compile(re.escape(t), re.IGNORECASE)
        if pattern.search(remaining):
            found.append(t)
            remaining = pattern.sub('', remaining)
    remaining = re.sub(r'\bet\b', ' ', remaining, flags=re.IGNORECASE)
    remaining = re.sub(r'\s*,\s*', ' ', remaining)
    remaining = re.sub(r'\s+', ' ', remaining).strip(' ,')
    return found, remaining


def parse_person_name(raw: str) -> dict:
    titles, rest = extract_titles(raw)
    tokens = rest.split()
    if not tokens:
        return dict(titul=', '.join(titles), jmeno='', prijmeni='')
    prijmeni = tokens[0]
    jmeno = ' '.join(tokens[1:])
    return dict(titul=', '.join(titles), jmeno=jmeno, prijmeni=prijmeni)


def guess_gender(jmeno: str, prijmeni: str):
    if not jmeno:
        return None, True
    jmeno_low = jmeno.split()[0].lower() if jmeno.split() else ''
    prijmeni_low = prijmeni.lower()

    if prijmeni_low.endswith('ová'):
        return 'F', jmeno_low in AMBIGUOUS_NAMES

    ambiguous = jmeno_low in AMBIGUOUS_NAMES

    if jmeno_low.endswith('a') and jmeno_low not in MALE_NAMES_ENDING_A:
        gender = 'F'
    elif jmeno_low.endswith('a') and jmeno_low in MALE_NAMES_ENDING_A:
        gender = 'M'
        ambiguous = True
    elif jmeno_low.endswith('ie'):
        gender = 'F'
    else:
        gender = 'M'

    return gender, ambiguous


# ---------------------------------------------------------------------------
# Rozpoznání právnické osoby
# ---------------------------------------------------------------------------

def is_company(name: str) -> bool:
    return any(p.search(name) for p in COMPANY_KEYWORD_PATTERNS)


# ---------------------------------------------------------------------------
# Sestavení výstupních řádků
# ---------------------------------------------------------------------------

def make_company_row(name: str, address: str, extra: str = '') -> dict:
    addr = parse_address(address) if address else dict(
        ulice='', cislo_domu='', psc='', obec='',
        kontrola=True, poznamka='Adresa chybí', puvodni_adresa=address or '',
    )
    poznamka_parts = ['Právnická osoba / organizace']
    if addr['poznamka']:
        poznamka_parts.append(addr['poznamka'])
    if extra:
        poznamka_parts.append(extra)
    return {
        'Oslovení': 'Vážení',
        'Titul': '',
        'Jméno': '',
        'Příjmení / Název': name.strip(),
        'Ulice': addr['ulice'],
        'Číslo domu': addr['cislo_domu'],
        'PSČ': addr['psc'],
        'Obec': addr['obec'],
        'Kontrola': 'ANO',
        'Poznámka': '; '.join(p for p in poznamka_parts if p),
        'Původní adresa': addr['puvodni_adresa'],
    }


def make_person_row(raw_name: str, address: str, extra: str = '') -> dict:
    parsed_name = parse_person_name(raw_name)
    gender, ambiguous = guess_gender(parsed_name['jmeno'], parsed_name['prijmeni'])

    if gender == 'F':
        osloveni_zaklad = 'Vážená paní'
        is_woman = True
    elif gender == 'M':
        osloveni_zaklad = 'Vážený pane'
        is_woman = False
    else:
        osloveni_zaklad = 'Vážený pane / Vážená paní'
        is_woman = None
        ambiguous = True

    osloveni = osloveni_zaklad
    declension_failed = False
    if gender in ('M', 'F') and parsed_name['prijmeni']:
        vokativ_prijmeni, ok = vocative_surname(parsed_name['prijmeni'], is_woman)
        if ok:
            osloveni = f'{osloveni_zaklad} {vokativ_prijmeni}'
        else:
            osloveni = f'{osloveni_zaklad} {parsed_name["prijmeni"]}'
            declension_failed = True

    kontrola = ambiguous
    poznamka_parts = []
    if extra:
        poznamka_parts.append(extra)
    if declension_failed:
        poznamka_parts.append('Příjmení se nepodařilo sklonit do 5. pádu - ponecháno v 1. pádu')
        kontrola = True

    if address:
        addr = parse_address(address)
        ulice, cislo, psc, obec = addr['ulice'], addr['cislo_domu'], addr['psc'], addr['obec']
        if addr['kontrola']:
            kontrola = True
        if addr['poznamka']:
            poznamka_parts.append(addr['poznamka'])
        puvodni = addr['puvodni_adresa']
    else:
        ulice = cislo = psc = obec = ''
        kontrola = True
        poznamka_parts.append('Adresa chybí')
        puvodni = ''

    if not parsed_name['jmeno'] or not parsed_name['prijmeni']:
        kontrola = True
        poznamka_parts.append('Jméno nebo příjmení se nepodařilo jednoznačně rozdělit')

    return {
        'Oslovení': osloveni,
        'Titul': parsed_name['titul'],
        'Jméno': parsed_name['jmeno'],
        'Příjmení / Název': parsed_name['prijmeni'],
        'Ulice': ulice,
        'Číslo domu': cislo,
        'PSČ': psc,
        'Obec': obec,
        'Kontrola': 'ANO' if kontrola else 'NE',
        'Poznámka': '; '.join(p for p in poznamka_parts if p),
        'Původní adresa': puvodni,
    }


def make_no_address_row(text: str, extra: str = '') -> dict:
    if is_company(text):
        return make_company_row(text, '', extra)
    return make_person_row(text, '', extra)


def split_name_address(text: str):
    if ',' not in text:
        return text.strip(), ''
    name_part, address_part = text.split(',', 1)
    name_part = name_part.strip()
    address_part = address_part.strip()

    title_set_lower = {t.lower() for t in TITLE_LIST}
    for _ in range(3):
        if ',' not in address_part:
            break
        first_tok, rest = address_part.split(',', 1)
        first_tok = first_tok.strip()
        if first_tok.lower() in title_set_lower:
            name_part = name_part + ', ' + first_tok
            address_part = rest.strip()
        else:
            break
    return name_part, address_part


def split_sjm_pair(rest: str):
    """
    Rozdělí text SJ deklarace (bez prefixu SJ/SJM/BSM/MCP) na
    (jméno1, jméno2, adresa). Adresa může být '' (bez adresy - uvedena
    jinde v PDF). Vrátí None, pokud se nepodaří najít dvě jména.

    Nejdřív se rozdělí podle spojky " a " (odděluje dvě osoby), TEPRVE
    POTOM se v druhé části hledá adresa - to je zásadní pro případy,
    kdy má první osoba víc titulů oddělených čárkou (např. "Novák Jan
    Mgr., Bc. a Nováková Jana, Adresa"), aby se čárka mezi tituly
    nespletla s hranicí adresy.
    """
    parts = re.split(r'\s+a\s+', rest, maxsplit=1)
    if len(parts) != 2:
        return None
    name1 = parts[0].strip()
    name2, address = split_name_address(parts[1])
    return name1, name2.strip(), address.strip()


def process_entry_text(entry_text: str):
    text = entry_text.strip()
    if not text:
        return []

    sjm_match = re.match(
        r'^' + JOINT_OWNERSHIP_PREFIXES + r'\b[:.]?\s*(.*)$', text, re.IGNORECASE
    )
    if sjm_match:
        rest = sjm_match.group(1).strip()
        split = split_sjm_pair(rest)
        if split:
            name1, name2, address_part = split
            if address_part:
                row1 = make_person_row(name1, address_part)
                row2 = make_person_row(name2, address_part)
                note = 'Adresa SJM použita pro oba manžele'
                for r in (row1, row2):
                    r['Poznámka'] = '; '.join(p for p in [r['Poznámka'], note] if p)
                return [row1, row2]
            else:
                return []
        else:
            name_part, address_part = split_name_address(rest)
            row = make_person_row(name_part, address_part)
            row['Kontrola'] = 'ANO'
            row['Poznámka'] = '; '.join(
                p for p in [row['Poznámka'],
                            'SJM se nepodařilo rozdělit na dvě osoby - zkontrolujte ručně']
                if p
            )
            return [row]

    if ',' in text:
        name_part, address_part = split_name_address(text)
        if is_company(name_part):
            return [make_company_row(name_part, address_part)]
        return [make_person_row(name_part, address_part)]

    return [make_no_address_row(text)]


def dedupe(rows):
    seen = set()
    out = []
    for r in rows:
        key = (
            r['Titul'].strip().lower(),
            r['Jméno'].strip().lower(),
            r['Příjmení / Název'].strip().lower(),
            r['Ulice'].strip().lower(),
            r['Číslo domu'].strip().lower(),
            r['PSČ'].strip().lower(),
            r['Obec'].strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def process_pdf_to_rows(file):
    """
    Hlavní vstupní funkce.
    `file` může být cesta k souboru nebo file-like objekt (např. z st.file_uploader).
    Vrací (rows, full_text, section_text, sjm_flags, units).
    `sjm_flags` je seznam bool hodnot stejné délky jako `rows` - True u
    řádků, které prokazatelně pocházejí ze zápisu "SJ" (společné jmění
    manželů) v PDF.
    `units` je seznam (stejné délky jako `rows`) s číslem vlastní bytové
    jednotky daného vlastníka (nebo None) - používá se jako doplňkový
    klíč pro spolehlivější rozpoznání manželů.
    """
    full_text = extract_full_text(file)
    section_text = extract_owners_section(full_text)

    if not section_text:
        return [], full_text, section_text, [], []

    entries = build_entries(section_text)

    rows = []
    sjm_flags = []
    units = []
    pending_roots = []  # [{'root': str, 'ttl': int, 'unit': str|None}, ...]

    for entry in entries:
        text = entry['text'].strip()
        entry_unit = entry['jednotka']
        if not text:
            continue

        sjm_match = re.match(
            r'^' + JOINT_OWNERSHIP_PREFIXES + r'\b[:.]?\s*(.*)$', text, re.IGNORECASE
        )
        if sjm_match:
            rest = sjm_match.group(1).strip()
            split = split_sjm_pair(rest)
            if split and split[2]:
                new_rows = process_entry_text(text)
                for r in new_rows:
                    rows.append(r)
                    sjm_flags.append(True)
                    units.append(entry_unit)
            elif split:
                name1, name2, _ = split
                for part_name in (name1, name2):
                    root = canonical_surname_root(parse_person_name(part_name)['prijmeni'])
                    if root:
                        pending_roots.append({'root': root, 'ttl': 3, 'unit': entry_unit})
            else:
                new_rows = process_entry_text(text)
                for r in new_rows:
                    rows.append(r)
                    sjm_flags.append(True)
                    units.append(entry_unit)
            continue

        new_rows = process_entry_text(text)
        for r in new_rows:
            prij_root = canonical_surname_root(r.get('Příjmení / Název', ''))
            matched = False
            matched_unit = entry_unit
            for p in pending_roots:
                if p['root'] and p['root'] == prij_root:
                    matched = True
                    matched_unit = p['unit'] or entry_unit
                    pending_roots.remove(p)
                    break
            rows.append(r)
            sjm_flags.append(matched)
            units.append(matched_unit)

        for p in pending_roots:
            p['ttl'] -= 1
        pending_roots = [p for p in pending_roots if p['ttl'] > 0]

    rows, sjm_flags, units = _dedupe_with_flags(rows, sjm_flags, units)
    return rows, full_text, section_text, sjm_flags, units


def _dedupe_with_flags(rows, flags, units):
    seen = set()
    out_rows = []
    out_flags = []
    out_units = []
    for r, f, u in zip(rows, flags, units):
        key = (
            r['Titul'].strip().lower(),
            r['Jméno'].strip().lower(),
            r['Příjmení / Název'].strip().lower(),
            r['Ulice'].strip().lower(),
            r['Číslo domu'].strip().lower(),
            r['PSČ'].strip().lower(),
            r['Obec'].strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        out_rows.append(r)
        out_flags.append(f)
        out_units.append(u)
    return out_rows, out_flags, out_units
