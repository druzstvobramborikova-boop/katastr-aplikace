# -*- coding: utf-8 -*-
"""
parser.py
Logika pro extrakci sekce "Vlastníci, jiní oprávnění" z PDF výpisu
z Nahlížení do katastru nemovitostí a její rozparsování do řádků
vhodných pro hromadnou korespondenci.

Formát vychází z reálných PDF z https://nahlizenidokn.cuzk.gov.cz/ :
- Jméno (jména) vlastníka a jeho adresa jsou typicky NA JEDNOM ŘÁDKU,
  oddělené čárkami: "Příjmení Jméno [tituly], Ulice č.p., Část obce, PSČ Obec"
- Po tomto řádku následuje řádek "Jednotka: ..." (případně přes více
  řádků) a řádek/y s podílem (zlomek typu "458/176969") - to vše se
  ignoruje (nejde o jméno ani adresu).
- Společné jmění manželů (SJM) se v reálných výpisech značí "SJ" (ne
  vždy "SJM"), případně jinými kódy ("BSM", "MCP" u cizinců apod.):
    - Pokud řádek "SJ Příjmení1 Jméno1 a Příjmení2 Jméno2" OBSAHUJE
      čárku a za ní adresu, jde o společnou adresu pro oba.
    - Pokud řádek čárku/adresu NEOBSAHUJE, adresy obou manželů jsou
      uvedeny zvlášť na následujících řádcích (každý jako normální
      "Jméno, Adresa" řádek) - ty se zpracují úplně stejně jako
      kterýkoli jiný vlastník, deklarační "SJ ..." řádek se v tomto
      případě jen přeskočí (informace z něj by byla duplicitní).
- PDF obsahuje uprostřed seznamu vlastníků opakovaně řádky se
  záhlavím/patičkou stránky (datum/čas, URL, číslo stránky) - ty se
  na začátku odstraní.

POZNÁMKA K SPOLEHLIVOSTI:
Tato pravidla vycházejí z konkrétních vzorků reálných PDF. Pokud se u
jiného typu výpisu (např. jiná verze generátoru Nahlížení) zformátování
mírně liší, podívejte se v aplikaci do "Debug" náhledu extrahovaného
textu - podle něj lze snadno doladit regulární výrazy níže.
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

# Tituly - pořadí v seznamu není podstatné, při hledání se řadí podle
# délky (viz extract_titles), aby se nejdřív odstranily delší varianty.
TITLE_LIST = [
    'PharmDr.', 'MUDr.', 'JUDr.', 'RNDr.', 'PhDr.', 'MVDr.', 'RSDr.',
    'Ph.D.', 'Ph.D', 'PhD.', 'PhD', 'Phd.',
    'DiS.', 'Ing. arch.', 'arch.', 'Ing.', 'Mgr.', 'Doc.', 'CSc.',
    'Bc.', 'MBA', 'M.A.', 'LL.M.',
]

# Klíčová slova pro rozpoznání právnické osoby / státu / organizace
# (porovnávají se jako celá slova, ne jako podřetězec - viz is_company)
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

# Jména, u kterých si nejsme jisti pohlavím (vzácná, dvojrodá apod.)
AMBIGUOUS_NAMES = {'nikola', 'saša', 'mája'}

# Mužská jména končící na "a", která by jinak heuristika vyhodnotila jako ženská
MALE_NAMES_ENDING_A = {'jura', 'pepa', 'honza'}

# Prefixy označující společné jmění manželů / spoluvlastnictví dvou osob
JOINT_OWNERSHIP_PREFIXES = r'(?:SJM|SJ|BSM|MCP)'

# Řádky, které nejsou jméno ani adresa (podíl, jednotka, RČ, IČO, hlavičky…)
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

# Hlavičky, kterými typicky sekce "Vlastníci, jiní oprávnění" v textu začíná
SECTION_START_PATTERNS = [
    r'Vlastníci,\s*jiní\s*oprávn[eě]n[ií]',
    r'Vlastník,\s*jiný\s*oprávněný',
]

# Hlavičky následujících sekcí, kterými extrakce končí
SECTION_END_MARKERS = [
    'Příslušnost hospodařit s majetkem státu',
    'Způsob ochrany nemovitosti',
    'Vlastnictví jednotek',
    'Jiné zápisy', 'Omezení vlastnického práva', 'Cizí věcná práva',
    'Plomby', 'Řízení, v rámci', 'Věcná břemena', 'Zástavní právo',
    'Související zápisy',
]

# Patičky / hlavičky stránek, které je vhodné z textu odstranit
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
    """Vrátí celý text PDF (po odstranění patiček/hlaviček stránek)."""
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
        if idx != -1:
            end_idx = min(end_idx, idx)

    return rest[:end_idx].strip()


# ---------------------------------------------------------------------------
# Seskupení textu sekce na jednotlivé záznamy ("Jméno, Adresa" řádky)
# ---------------------------------------------------------------------------

def is_noise_line(line: str) -> bool:
    if any(p.search(line) for p in NOISE_PATTERNS):
        return True
    # řádek bez jediného písmene (pokračování seznamu jednotek, samotný
    # zlomek podílu apod.) není ani jméno, ani adresa
    if not any(ch.isalpha() for ch in line):
        return True
    return False


def build_entries(section_text: str):
    """
    Rozdělí text sekce na jednotlivé záznamy (řetězce).

    Princip: každý netriviální ("obsahový") řádek je buď:
    - kompletní záznam "Jméno, Adresa" (obvykle obsahuje čárku),
    - samostatné jméno bez adresy (např. "Česká republika", nebo
      deklarace "SJ Příjmení1 Jméno1 a Příjmení2 Jméno2" bez adresy -
      v tom případě jsou skutečné adresy uvedeny na následujících
      řádcích jako vlastní kompletní záznamy),
    - nebo pokračování (zalomení) předchozího řádku přes stránku/šířku
      (typicky bez čárky a bezprostředně navazující na předchozí
      obsahový řádek bez "šumu" mezi nimi).
    """
    raw_lines = [l.strip() for l in section_text.split('\n')]
    raw_lines = [l for l in raw_lines if l]

    entries = []
    prev_was_content = False

    for line in raw_lines:
        if is_noise_line(line):
            prev_was_content = False
            continue

        prev_ends_with_hyphen = bool(entries) and entries[-1].rstrip().endswith('-')

        if prev_was_content and entries and (',' not in line or prev_ends_with_hyphen):
            if prev_ends_with_hyphen:
                # rozdělené slovo/místní část přes konec řádku (např. "Liberec
                # XIV-" / "Ruprechtice") - spojíme bez mezery
                entries[-1] = entries[-1] + line
            else:
                # běžné zalomení (wrap) předchozího řádku
                entries[-1] = entries[-1] + ' ' + line
        else:
            entries.append(line)

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

    # Pokud se na konec obce omylem přilepil zlomek podílu (důsledek
    # specifického zalomení řádků v PDF u některých záznamů), odstraníme ho.
    frac_match = re.search(r'\s+\d+\s*/\s*\d+\s*$', obec)
    if frac_match:
        obec = obec[:frac_match.start()].strip()
        notes.append('Odstraněn zlomek podílu omylem připojený k obci')

    if parts:
        street_part = parts[0]
        cp_match = re.match(r'^(č\.?\s?(p|ev)\.?\s?\d+\w*)$', street_part, re.IGNORECASE)
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
    # spojky mezi tituly typu "Ing. et Bc." - odstraníme osamocené "et"
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
    """Vrátí ('M'|'F'|None, ambiguous: bool)."""
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


def make_no_address_row(text: str, extra: str = '') -> dict:
    """Záznam bez adresy (stát, organizace, nebo vlastník, jehož adresa
    se v textu nepodařilo najít)."""
    if is_company(text):
        return make_company_row(text, '', extra)
    return make_person_row(text, '', extra)


def split_name_address(text: str):
    """
    Rozdělí text na (jméno, adresa) podle první čárky - ALE pokud část
    hned za čárkou je sama o sobě jen titul (např. ", MBA" u "PhDr.
    Ph.D., MBA, Kyselova ..."), spojí ji zpátky ke jménu a zkusí další
    čárku. Zabraňuje tomu, aby titul za čárkou skončil omylem v adrese.
    """
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


def process_entry_text(entry_text: str):
    text = entry_text.strip()
    if not text:
        return []

    sjm_match = re.match(
        r'^' + JOINT_OWNERSHIP_PREFIXES + r'\b[:.]?\s*(.*)$', text, re.IGNORECASE
    )
    if sjm_match:
        rest = sjm_match.group(1).strip()
        if ',' in rest:
            name_part, address_part = split_name_address(rest)
            parts = re.split(r'\s+a\s+', name_part, maxsplit=1)
            if len(parts) == 2:
                row1 = make_person_row(parts[0].strip(), address_part)
                row2 = make_person_row(parts[1].strip(), address_part)
                note = 'Adresa SJM použita pro oba manžele'
                for r in (row1, row2):
                    r['Poznámka'] = '; '.join(p for p in [r['Poznámka'], note] if p)
                return [row1, row2]
            else:
                row = make_person_row(rest, address_part)
                row['Kontrola'] = 'ANO'
                row['Poznámka'] = '; '.join(
                    p for p in [row['Poznámka'],
                                'SJM se nepodařilo rozdělit na dvě osoby - zkontrolujte ručně']
                    if p
                )
                return [row]
        else:
            # bez adresy - skutečné adresy manželů jsou na následujících
            # samostatných řádcích, které se zpracují jako normální
            # vlastníci. Tento deklarační řádek proto přeskočíme.
            return []

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
    Vrací (rows, full_text, section_text).
    """
    full_text = extract_full_text(file)
    section_text = extract_owners_section(full_text)

    if not section_text:
        return [], full_text, section_text

    entries = build_entries(section_text)

    rows = []
    for entry_text in entries:
        rows.extend(process_entry_text(entry_text))

    rows = dedupe(rows)
    return rows, full_text, section_text
