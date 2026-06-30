# -*- coding: utf-8 -*-
"""
parser.py
Logika pro extrakci sekce "Vlastníci, jiní oprávnění" z PDF výpisu
z Nahlížení do katastru nemovitostí a její rozparsování do řádků
vhodných pro hromadnou korespondenci.

POZNÁMKA K SPOLEHLIVOSTI:
Formát PDF z Nahlížení do katastru se může mírně lišit podle typu
výpisu (LV, informace o stavbě, informace o pozemku) a podle toho, jak
pdfplumber text z PDF přečte (ztráta sloupců/odsazení je u PDF běžná).
Parser proto pracuje s heuristikami popsanými v komentářích. Pokud
parser u konkrétního PDF něco rozpozná špatně, nejprve se podívejte
do "debug" náhledu extrahovaného textu v aplikaci (sekce "Vlastníci,
jiní oprávnění") - podle něj lze snadno doladit regulární výrazy níže.
"""

import re
import pdfplumber

# ---------------------------------------------------------------------------
# Konstanty / slovníky
# ---------------------------------------------------------------------------

COLUMNS = [
    'Oslovení', 'Titul', 'Jméno', 'Příjmení / Název',
    'Ulice', 'Číslo domu', 'PSČ', 'Obec',
    'Kontrola', 'Poznámka', 'Původní adresa',
]

# Tituly - řazeno od nejdelších, aby např. "Ph.D." nebylo "sežráno" jako "D."
TITLE_LIST = [
    'PharmDr.', 'MUDr.', 'JUDr.', 'RNDr.', 'PhDr.', 'MVDr.', 'RSDr.',
    'Ph.D.', 'DiS.', 'Ing.', 'Mgr.', 'Doc.', 'CSc.', 'Bc.', 'MBA',
]

# Klíčová slova pro rozpoznání právnické osoby / státu / organizace
COMPANY_KEYWORDS = [
    's.r.o', 'a.s.', 'k.s.', 'v.o.s', 'spol. s r', 'družstvo',
    'státní podnik', ' s.p.', 'česká republika', 'spolek', 'nadace',
    'nadační fond', 'fond', 'církev', 'farnost', 'diecéze', 'obec ',
    'město ', 'statutární město', 'kraj', 'společenství vlastníků',
    'úřad', 'ministerstvo', 'organizační složka', 'příspěvková organizace',
    'ústav', 'akciová společnost', 'svaz', 'svazek obcí', 'sdružení',
    'gmbh', ' ltd', 'inc.', 'b.v.', 'sp. z o.o', 'kft', 's.a.', 'plc',
]

# Jména, u kterých si nejsme jisti pohlavím (vzácná, dvojrodá apod.)
AMBIGUOUS_NAMES = {'nikola', 'saša', 'mája'}

# Mužská jména končící na "a", která by jinak heuristika vyhodnotila jako ženská
MALE_NAMES_ENDING_A = {'jura', 'pepa', 'honza', 'nikola'}

# Řádky, které nejsou součástí jména ani adresy (podíl, jednotka, RČ, IČO...)
NOISE_PATTERNS = [
    re.compile(r'^podíl', re.IGNORECASE),
    re.compile(r'^\s*\d+\s*/\s*\d+\s*$'),
    re.compile(r'^jednotka', re.IGNORECASE),
    re.compile(r'^nar\.', re.IGNORECASE),
    re.compile(r'^rč[:.]', re.IGNORECASE),
    re.compile(r'^r\.?\s*č\.?[:.]', re.IGNORECASE),
    re.compile(r'^datum narození', re.IGNORECASE),
    re.compile(r'^i[čc]o\b', re.IGNORECASE),
    re.compile(r'^typ vztahu', re.IGNORECASE),
    re.compile(r'^způsob ochrany', re.IGNORECASE),
]

# Hlavičky, kterými typicky sekce "Vlastníci, jiní oprávnění" v textu začíná
SECTION_START_PATTERNS = [
    r'Vlastníci,\s*jiní\s*oprávn[eě]n[ií]',
    r'Vlastník,\s*jiný\s*oprávněný',
]

# Hlavičky následujících sekcí, kterými extrakce končí
SECTION_END_MARKERS = [
    'Jiné zápisy', 'Omezení vlastnického práva', 'Cizí věcná práva',
    'Nemovitosti', 'Plomby', 'Řízení', 'Věcná břemena', 'Zástavní právo',
    'Související zápisy', 'Poznámka:',
]

# Patičky / hlavičky stránek, které je vhodné z textu odstranit
FOOTER_LINE_PATTERNS = [
    re.compile(r'^Strana\s*\d+', re.IGNORECASE),
    re.compile(r'^Vyhotoveno', re.IGNORECASE),
    re.compile(r'^www\.cuzk\.cz', re.IGNORECASE),
    re.compile(r'^Nahlížení do katastru nemovitostí\s*$', re.IGNORECASE),
    re.compile(r'^Český úřad zeměměřický', re.IGNORECASE),
]

PSC_RE = re.compile(r'(\d{3}\s?\d{2})\s+(.+)$')


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
    """Vrátí celý text PDF (po odstranění patiček)."""
    chunks = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ''
            chunks.append(t)
    return _clean_full_text('\n'.join(chunks))


def extract_owners_section(full_text: str) -> str:
    """Vyřízne ze zadaného textu pouze sekci 'Vlastníci, jiní oprávnění'."""
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
        # ignorujeme nálezy hned na začátku (mohlo by jít o nadpis tabulky)
        if idx != -1 and idx > 15:
            end_idx = min(end_idx, idx)

    return rest[:end_idx].strip()


# ---------------------------------------------------------------------------
# Rozdělení sekce na jednotlivé "bloky" vlastníků (jméno + adresa)
# ---------------------------------------------------------------------------

def split_into_entries(section_text: str):
    """
    Heuristicky rozdělí text sekce na jednotlivé záznamy vlastníků.

    Princip: řádek BEZ číslice je obvykle jméno (osoby nebo firmy),
    řádek S číslicí je obvykle adresa (obsahuje číslo popisné a/nebo PSČ).
    Řádky odpovídající "šumu" (podíl, jednotka, RČ, IČO...) se ukládají
    zvlášť do poznámky a nepoužívají se pro adresu.

    Adresové řádky se ukládají jako SEZNAM (ne rovnou spojené do jednoho
    řetězce), aby šlo později spolehlivě poznat, jestli SJM uvádí jednu
    společnou adresu, nebo dvě adresy na dvou samostatných řádcích.
    """
    entries = []
    current_name_lines = []
    current_addr_lines = []
    current_extra = []

    def flush():
        if current_name_lines:
            entries.append({
                'name': ' '.join(current_name_lines).strip(),
                'address_lines': list(current_addr_lines),
                'extra': '; '.join(current_extra),
            })

    for raw_line in section_text.split('\n'):
        line = raw_line.strip()
        if not line:
            continue
        if any(p.search(line) for p in NOISE_PATTERNS):
            current_extra.append(line)
            continue

        has_digit = bool(re.search(r'\d', line))
        if not has_digit:
            if current_addr_lines:
                # adresa už začala -> tento řádek bez číslice je nové jméno
                flush()
                current_name_lines = [line]
                current_addr_lines = []
                current_extra = []
            else:
                current_name_lines.append(line)
        else:
            current_addr_lines.append(line)

    flush()
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
        # zkusíme, jestli PSČ a obec nejsou rozdělené do dvou posledních částí
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
                notes.append('PSČ nerozpoznáno')
        else:
            obec = last
            parts = []
            kontrola = True
            notes.append('PSČ nerozpoznáno')

    ulice = ''
    cislo_domu = ''
    if parts:
        street_part = parts[0]
        cp_match = re.match(r'^(č\.?\s?p\.?\s?\d+\w*)$', street_part, re.IGNORECASE)
        if cp_match:
            cislo_domu = street_part
            ulice = ''
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
    else:
        if not obec:
            kontrola = True
            notes.append('Ulice / číslo domu nenalezeno')

    return dict(
        ulice=ulice, cislo_domu=cislo_domu, psc=psc, obec=obec,
        kontrola=kontrola, poznamka='; '.join(notes),
        puvodni_adresa=original,
    )


def join_address_lines(address_lines):
    """Spojí řádky adresy do jednoho řetězce vhodného pro parse_address()."""
    return ', '.join(l.strip().rstrip(',') for l in address_lines if l.strip())


# ---------------------------------------------------------------------------
# Parsování jména a titulu
# ---------------------------------------------------------------------------

def extract_titles(text: str):
    found = []
    remaining = text
    for t in TITLE_LIST:
        pattern = re.compile(re.escape(t), re.IGNORECASE)
        if pattern.search(remaining):
            found.append(t)
            remaining = pattern.sub('', remaining)
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
    """Vrátí ('M'|'F'|None, ambiguous: bool)."""
    if not jmeno:
        return None, True
    jmeno_low = jmeno.split()[0].lower() if jmeno.split() else ''
    prijmeni_low = prijmeni.lower()

    # Příjmení na "-ová" je v češtině velmi spolehlivý signál ženského rodu
    if prijmeni_low.endswith('ová'):
        return 'F', jmeno_low in AMBIGUOUS_NAMES

    ambiguous = jmeno_low in AMBIGUOUS_NAMES

    if jmeno_low.endswith('a') and jmeno_low not in MALE_NAMES_ENDING_A:
        gender = 'F'
    elif jmeno_low.endswith('a') and jmeno_low in MALE_NAMES_ENDING_A:
        gender = 'M'
        ambiguous = True
    elif jmeno_low.endswith('ie'):
        # např. Marie, Lucie, Julie, Žofie, Natálie, Amálie
        gender = 'F'
    else:
        gender = 'M'

    return gender, ambiguous


# ---------------------------------------------------------------------------
# Rozpoznání právnické osoby
# ---------------------------------------------------------------------------

def is_company(name: str) -> bool:
    low = f' {name.lower()} '
    return any(k in low for k in COMPANY_KEYWORDS)


# ---------------------------------------------------------------------------
# Sestavení výstupních řádků
# ---------------------------------------------------------------------------

def make_company_row(name: str, address: str, extra: str) -> dict:
    if address:
        addr = parse_address(address)
    else:
        addr = dict(ulice='', cislo_domu='', psc='', obec='',
                    kontrola=True, poznamka='Adresa chybí', puvodni_adresa='')
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


def make_person_row(raw_name: str, address: str, extra: str) -> dict:
    parsed_name = parse_person_name(raw_name)
    gender, ambiguous = guess_gender(parsed_name['jmeno'], parsed_name['prijmeni'])

    if gender == 'F':
        osloveni = 'Vážená paní'
    elif gender == 'M':
        osloveni = 'Vážený pane'
    else:
        osloveni = 'Vážený pane / Vážená paní'
        ambiguous = True

    kontrola = ambiguous
    poznamka_parts = []
    if extra:
        poznamka_parts.append(extra)

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


def process_owner_entry(entry: dict):
    name = entry['name'].strip()
    address_lines = entry.get('address_lines', [])
    extra = entry['extra'].strip()
    rows = []

    if not name:
        return rows

    if is_company(name):
        address = join_address_lines(address_lines)
        rows.append(make_company_row(name, address, extra))
        return rows

    sjm_match = re.match(r'^SJM\b[:.]?\s*(.*)$', name, re.IGNORECASE)
    if sjm_match:
        name_wo_sjm = sjm_match.group(1).strip()
        parts = re.split(r'\s+a\s+', name_wo_sjm, maxsplit=1)
        if len(parts) == 2:
            p1_name, p2_name = parts[0].strip(), parts[1].strip()

            if len(address_lines) == 1:
                # jedna společná adresa na řádku SJM -> použije se pro oba
                addr1 = addr2 = join_address_lines(address_lines)
                shared_note = 'Adresa SJM použita pro oba manžele'
            elif len(address_lines) == 2:
                # dva samostatné řádky adresy -> každému manželovi jeho vlastní
                addr1 = join_address_lines([address_lines[0]])
                addr2 = join_address_lines([address_lines[1]])
                shared_note = None
            elif len(address_lines) == 0:
                addr1 = addr2 = ''
                shared_note = None
            else:
                # nejednoznačný počet řádků adresy -> spojit a nechat zkontrolovat
                addr1 = addr2 = join_address_lines(address_lines)
                shared_note = ('Nejednoznačný počet řádků adresy u SJM '
                                '(spojeno dohromady) - zkontrolujte ručně')

            row1 = make_person_row(p1_name, addr1, extra)
            row2 = make_person_row(p2_name, addr2, extra)
            if shared_note:
                for r in (row1, row2):
                    r['Poznámka'] = '; '.join(p for p in [r['Poznámka'], shared_note] if p)
                    if 'počet řádků' in shared_note:
                        r['Kontrola'] = 'ANO'
            rows.extend([row1, row2])
        else:
            address = join_address_lines(address_lines)
            row = make_person_row(name_wo_sjm, address, extra)
            row['Kontrola'] = 'ANO'
            row['Poznámka'] = '; '.join(
                p for p in [row['Poznámka'], 'SJM se nepodařilo rozdělit na dvě osoby - zkontrolujte ručně'] if p
            )
            rows.append(row)
        return rows

    address = join_address_lines(address_lines)
    rows.append(make_person_row(name, address, extra))
    return rows


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
    Vrací (rows, full_text, section_text).
    """
    full_text = extract_full_text(file)
    section_text = extract_owners_section(full_text)

    if not section_text:
        return [], full_text, section_text

    entries = split_into_entries(section_text)

    rows = []
    for entry in entries:
        rows.extend(process_owner_entry(entry))

    rows = dedupe(rows)
    return rows, full_text, section_text
