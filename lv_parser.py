# -*- coding: utf-8 -*-
"""
lv_parser.py
Zpracování kompletního "VÝPIS Z KATASTRU NEMOVITOSTÍ" (list vlastnictví
s jednotkami vymezenými podle zákona č. 72/1994 Sb.).

Na rozdíl od parser.py (které zpracovává jednodušší "Informace o stavbě"
PDF), tento typ výpisu má dvě části, které je nutné propojit:

- Část A: seznam vlastníků se jménem, ADRESOU, rodným číslem / IČO
  (identifikátor) a podílem na společných částech domu.
- Část B: seznam BYTOVÝCH JEDNOTEK, ke každé jednotce jméno vlastníka /
  vlastníků a jejich rodné číslo / IČO (ale BEZ adresy).

Propojujeme je přes rodné číslo / IČO (identifikátor). Pro malý počet
vlastníků (typicky zahraniční osoby bez standardního rodného čísla),
kde se identifikátor nepodařilo spolehlivě rozpoznat, se použije
záložní spárování podle jména.

Část A se čte pomocí souřadnic slov (ne jen prostého textu), protože
sloupce "Vlastník", "Identifikátor" a "Podíl" se v obyčejném textovém
exportu PDF proplétají.
"""

import re
import pdfplumber

from parser import (
    TITLE_LIST, COMPANY_KEYWORD_PATTERNS, AMBIGUOUS_NAMES,
    MALE_NAMES_ENDING_A, JOINT_OWNERSHIP_PREFIXES,
    extract_titles, parse_person_name, guess_gender, is_company,
    PSC_RE, vocative_surname,
)

LV_COLUMNS = [
    'Bytová jednotka', 'Oslovení', 'Jméno', 'Příjmení', 'Titul',
    'Ulice', 'Obec', 'PSČ', 'Kontrola', 'Poznámka', 'Původní adresa',
]

ID_TOKEN_RE = re.compile(r'\d{6}/\d{3,4}|\d{8}-\d{3}|\d{8}')
PODIL_SEARCH_RE = re.compile(r'\d+/\d{5,}')

VLASTNIK_X0_MAX = 370
RIGHT_COL_X0_MIN = 370


# ---------------------------------------------------------------------------
# Detekce typu dokumentu
# ---------------------------------------------------------------------------

def is_lv_document(full_text: str) -> bool:
    return bool(re.search(r'^A Vlastník', full_text, re.MULTILINE)) and \
        bool(re.search(r'^B Nemovitosti', full_text, re.MULTILINE))


# ---------------------------------------------------------------------------
# Část A - čtení podle souřadnic slov
# ---------------------------------------------------------------------------

PART_A_NOISE_PATTERNS = [
    re.compile(r'^VÝPIS Z KATASTRU NEMOVITOSTÍ', re.IGNORECASE),
    re.compile(r'^prokazující stav evidovaný', re.IGNORECASE),
    re.compile(r'^Vlastnictví domu s jednotkami', re.IGNORECASE),
    re.compile(r'^Okres:', re.IGNORECASE),
    re.compile(r'^Kat\.území:', re.IGNORECASE),
    re.compile(r'^V kat\. území jsou pozemky', re.IGNORECASE),
    re.compile(r'^A Vlastník', re.IGNORECASE),
    re.compile(r'^Vlastnické právo\s*$', re.IGNORECASE),
    re.compile(r'^Nemovitosti jsou v územním obvodu', re.IGNORECASE),
    re.compile(r'^Katastrální úřad pro', re.IGNORECASE),
    re.compile(r'^strana\s*\d+', re.IGNORECASE),
    re.compile(r'^SJ = společné jmění', re.IGNORECASE),
]


def _cluster_lines(words, tol=2.5):
    """Seskupí slova do řádků podle 'top' souřadnice (s tolerancí),
    v rámci řádku seřazeno zleva doprava. Vrací [(top, text), ...]."""
    words = sorted(words, key=lambda w: (round(w['top']), w['x0']))
    lines = []
    cur_top = None
    cur_words = []
    for w in words:
        if cur_top is None or abs(w['top'] - cur_top) <= tol:
            cur_words.append(w)
            if cur_top is None:
                cur_top = w['top']
        else:
            lines.append((round(cur_top, 1), ' '.join(x['text'] for x in cur_words)))
            cur_words = [w]
            cur_top = w['top']
    if cur_words:
        lines.append((round(cur_top, 1), ' '.join(x['text'] for x in cur_words)))
    return lines


def _merge_wrapped_fractions(lines):
    """Pokud se zlomek (identifikátor/podíl) zalomí přes okraj sloupce,
    pokračování ('/NNNN') se může objevit buď jako samostatný řádek,
    nebo smíchané na stejném řádku s dalším identifikátorem (u SJ
    párů). V obou případech ho spojíme zpátky k předchozímu řádku."""
    out = []
    for top, txt in lines:
        tokens = txt.split(' ')
        continuations = [t for t in tokens if re.match(r'^/\d+$', t)]
        remaining = [t for t in tokens if not re.match(r'^/\d+$', t)]
        if continuations and out:
            prev_top, prev_txt = out[-1]
            out[-1] = (prev_top, prev_txt + ''.join(continuations))
        if remaining:
            out.append((top, ' '.join(remaining)))
    return out


def _find_part_a_page_range(pdf):
    """Vrátí (start_page_idx, end_page_idx, end_page_top_limit).
    end_page_top_limit: pokud není None, na stránce s indexem
    end_page_idx-1 se mají brát v potaz jen řádky NAD touto souřadnicí
    (tam, kde na téže stránce začíná 'B Nemovitosti')."""
    start_idx = None
    end_idx = None
    end_top_limit = None
    for i, page in enumerate(pdf.pages):
        t = page.extract_text() or ''
        if start_idx is None and re.search(r'^A Vlastník', t, re.MULTILINE):
            start_idx = i
        if re.search(r'^B Nemovitosti', t, re.MULTILINE):
            end_idx = i + 1
            for w in page.extract_words():
                if w['text'] == 'B':
                    same_line = [x for x in page.extract_words()
                                 if abs(x['top'] - w['top']) < 2 and x['x0'] >= w['x0']]
                    same_line_text = ' '.join(x['text'] for x in sorted(same_line, key=lambda x: x['x0']))
                    if same_line_text.startswith('B Nemovitosti'):
                        end_top_limit = w['top']
                        break
            break
    if start_idx is None:
        start_idx = 0
    if end_idx is None:
        end_idx = len(pdf.pages)
    return start_idx, end_idx, end_top_limit


def extract_part_a_entries(pdf):
    """
    Přečte část A pomocí souřadnic a vrátí seznam záznamů:
    [{'name_address': str, 'ids': [str, ...]}, ...]
    """
    start_idx, end_idx, end_top_limit = _find_part_a_page_range(pdf)

    all_vlastnik = []
    all_right = []
    page_offset = 0
    for pnum in range(start_idx, end_idx):
        page = pdf.pages[pnum]
        words = page.extract_words()
        if pnum == end_idx - 1 and end_top_limit is not None:
            words = [w for w in words if w['top'] < end_top_limit - 0.5]
        vl_words = [w for w in words if w['x0'] < VLASTNIK_X0_MAX]
        right_words = [w for w in words if w['x0'] >= RIGHT_COL_X0_MIN]

        vlines = _cluster_lines(vl_words)
        vlines = [(t, txt) for t, txt in vlines
                  if not any(p.search(txt.strip()) for p in PART_A_NOISE_PATTERNS)]
        rlines = _merge_wrapped_fractions(_cluster_lines(right_words))

        for top, text in vlines:
            all_vlastnik.append((page_offset + top, text))
        for top, text in rlines:
            all_right.append((page_offset + top, text))
        page_offset += 2000

    podil_rows = []
    for t, txt in all_right:
        m = PODIL_SEARCH_RE.search(txt)
        if m:
            podil_rows.append((t, m.group(0)))
    podil_rows.sort()

    boundaries = [t for t, _ in podil_rows] + [float('inf')]
    entries = []
    for i, (t, podil_txt) in enumerate(podil_rows):
        start, end = t - 0.5, boundaries[i + 1]
        vl_text = ' '.join(txt for vt, txt in all_vlastnik if start <= vt < end)
        right_text = ' '.join(txt for rt, txt in all_right if start <= rt < end)
        id_text = right_text.replace(podil_txt, '', 1)
        ids = ID_TOKEN_RE.findall(id_text)
        entries.append({'name_address': vl_text.strip(), 'ids': ids})

    entries = _split_double_sjm_entries(entries)
    return entries


def _split_double_sjm_entries(entries):
    """Ve vzácných případech (chyba v souřadnicovém zalomení) skončí dvě
    SJ domácnosti v jednom záznamu. Pokud se v textu objeví prefix
    SJ/MCP/BSM VÍCEKRÁT, rozdělíme záznam na víc částí a rozdělíme mu i
    identifikátory po dvou."""
    prefix_re = re.compile(r'\b(?:SJ|MCP|BSM)\s', re.IGNORECASE)
    out = []
    for e in entries:
        matches = list(prefix_re.finditer(e['name_address']))
        if len(matches) <= 1:
            out.append(e)
            continue
        starts = [m.start() for m in matches] + [len(e['name_address'])]
        ids = list(e['ids'])
        for i in range(len(starts) - 1):
            chunk = e['name_address'][starts[i]:starts[i + 1]].strip()
            chunk_ids = ids[i * 2:i * 2 + 2] if len(ids) >= (i + 1) * 2 else ids[i * 2:]
            out.append({'name_address': chunk, 'ids': chunk_ids})
    return out


PSC_FINDALL_RE = re.compile(r'\d{3}\s?\d{2}\s+[^,]+')


def _split_two_address_text(address_part: str):
    """Pokud text adresy obsahuje dvě PSČ (dvě adresy manželů za sebou
    bez jasného oddělovače), rozdělí ho na dvě části. Jinak vrátí None."""
    parts = [p.strip() for p in address_part.split(',') if p.strip()]
    psc_idx = [i for i, p in enumerate(parts) if PSC_RE.search(p)]
    if len(psc_idx) == 2:
        i1, i2 = psc_idx
        addr1 = ', '.join(parts[:i1 + 1])
        addr2 = ', '.join(parts[i1 + 1:i2 + 1])
        return addr1, addr2
    return None


def build_id_address_maps(entries):
    """
    Z entries (Část A) sestaví:
    - id_to_address: identifikátor -> adresní text (za první čárkou)
    - name_to_address: normalizované jméno -> adresní text (záložní klíč)
    """
    id_to_address = {}
    name_to_address = {}

    for e in entries:
        text = e['name_address'].strip()
        if not text:
            continue

        m = re.match(r'^(?:SJ|MCP|BSM)\s+(.*)$', text, re.IGNORECASE)
        core = m.group(1) if m else text

        if ',' in core:
            name_part, address_part = core.split(',', 1)
            address_part = address_part.strip()
        else:
            name_part, address_part = core, ''

        for owner_id in e['ids']:
            if owner_id:
                id_to_address[owner_id] = address_part

        if len(e['ids']) == 2:
            split = _split_two_address_text(address_part)
            if split:
                id_to_address[e['ids'][0]] = split[0]
                id_to_address[e['ids'][1]] = split[1]

        for single_name in re.split(r'\s+a\s+', name_part):
            key = _normalize_name_key(single_name)
            if key:
                name_to_address[key] = address_part

        key_full = _normalize_name_key(name_part)
        if key_full:
            name_to_address[key_full] = address_part

    return id_to_address, name_to_address


def _normalize_name_key(name: str) -> str:
    _, rest = extract_titles(name)
    return re.sub(r'\s+', ' ', rest).strip().lower()


# ---------------------------------------------------------------------------
# Část B - jednotky a jejich vlastníci (z prostého textu)
# ---------------------------------------------------------------------------

UNIT_LINE_RE = re.compile(r'^(\d+/\d+)\s+([A-Za-zÁ-Žá-ž][\w á-žÁ-Ž]*?)\s+\d+\s+\S+\s+[\d/]+\s*$')

B_NOISE_PATTERNS = [
    re.compile(r'^VÝPIS Z KATASTRU NEMOVITOSTÍ', re.IGNORECASE),
    re.compile(r'^prokazující stav evidovaný', re.IGNORECASE),
    re.compile(r'^Okres:', re.IGNORECASE),
    re.compile(r'^Kat\.území:', re.IGNORECASE),
    re.compile(r'^V kat\. území jsou pozemky', re.IGNORECASE),
    re.compile(r'^Typ stavby\s*$', re.IGNORECASE),
    re.compile(r'^Část obce, č\. budovy', re.IGNORECASE),
    re.compile(r'^Podíl na\s*$', re.IGNORECASE),
    re.compile(r'^Č\.p\./ Typ', re.IGNORECASE),
    re.compile(r'^Č\.jednotky Způsob využití', re.IGNORECASE),
    re.compile(r'^Nemovitosti jsou v územním obvodu', re.IGNORECASE),
    re.compile(r'^Katastrální úřad pro', re.IGNORECASE),
    re.compile(r'^strana\s*\d+', re.IGNORECASE),
    re.compile(r'^Stavby\s*$', re.IGNORECASE),
    re.compile(r'^[\wÁ-Žá-ž ]+, č\.p\. \d+ ', re.IGNORECASE),
]


def extract_part_b_text(full_text: str) -> str:
    start_m = re.search(r'^B Nemovitosti', full_text, re.MULTILINE)
    if not start_m:
        return ''
    rest = full_text[start_m.end():]
    end_m = re.search(r'^B1 ', rest, re.MULTILINE)
    if end_m:
        rest = rest[:end_m.start()]
    return rest


def parse_part_b_units(part_b_text: str):
    """
    Vrátí seznam jednotek:
    [{'unit': '1185/1', 'typ_vyuziti': 'byt', 'owner_lines': [...]}]
    """
    lines = [l.strip() for l in part_b_text.split('\n') if l.strip()]

    units = []
    current_unit = None
    current_owner_lines = []

    def flush_unit():
        if current_unit is not None:
            current_unit['owner_lines'] = current_owner_lines
            units.append(current_unit)

    for line in lines:
        if any(p.search(line) for p in B_NOISE_PATTERNS):
            continue

        m = UNIT_LINE_RE.match(line)
        if m:
            flush_unit()
            current_unit = {'unit': m.group(1), 'typ_vyuziti': m.group(2).strip()}
            current_owner_lines = []
            continue

        if current_unit is None:
            continue

        low = line.lower()
        if low.startswith('spoluvlastníci'):
            rest = line[len('spoluvlastníci'):].strip()
            if rest:
                current_owner_lines.append(rest)
            continue

        if ';' in line:
            current_owner_lines.append(line)
        else:
            if current_owner_lines:
                current_owner_lines[-1] = current_owner_lines[-1] + ' ' + line

    flush_unit()
    return units


SHARE_TRAILING_RE = re.compile(r'\s+\d+/\d+\s*$')


def parse_owner_line(owner_line: str):
    """
    Rozparsuje jeden 'ID [ID2]; Jméno [podíl_na_jednotce]' řádek na
    seznam (id, name, is_sjm) trojic. is_sjm je True, pokud řádek
    obsahoval DVA identifikátory spojené "a" mezi jmény - to v tomto
    formátu PDF spolehlivě znamená společné jmění manželů (SJ).
    """
    if ';' not in owner_line:
        return []
    id_part, rest = owner_line.split(';', 1)
    id_part = id_part.strip()
    rest = rest.strip()

    rest = SHARE_TRAILING_RE.sub('', rest).strip()

    ids = ID_TOKEN_RE.findall(id_part)

    if len(ids) == 2:
        parts = re.split(r'\s+a\s+', rest, maxsplit=1)
        if len(parts) == 2:
            return [(ids[0], parts[0].strip(), True), (ids[1], parts[1].strip(), True)]
        return [(ids[0], rest, False), (ids[1], '', False)]

    single_id = ids[0] if ids else ''
    return [(single_id, rest, False)]


# ---------------------------------------------------------------------------
# Sestavení výstupních řádků
# ---------------------------------------------------------------------------

def _address_to_fields(address_text: str):
    """Rozdělí adresní text na (ulice_s_cislem, obec, psc, kontrola, poznamka)."""
    if not address_text:
        return '', '', '', True, 'Adresa chybí'

    parts = [p.strip() for p in address_text.split(',') if p.strip()]
    if not parts:
        return '', '', '', True, 'Adresa chybí'

    psc = ''
    obec = ''
    kontrola = False
    notes = []

    last = parts[-1]
    m = PSC_RE.search(last)
    if m:
        psc_raw = re.sub(r'\s+', '', m.group(1))
        psc = psc_raw[:3] + ' ' + psc_raw[3:]
        obec = m.group(2).strip()
        parts = parts[:-1]
    elif len(parts) >= 2:
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
    if parts:
        ulice = parts[0]
        if len(parts) > 1:
            district = ', '.join(parts[1:])
            notes.append(f'Městská část / část obce v adrese (do Ulice nezahrnuto): "{district}"')
        else:
            kontrola = True
            notes.append(
                f'Nejisté, zda "{ulice}" je skutečná ulice, nebo jde o název '
                'obce/vesnice bez ulice - zkontrolujte'
            )

    return ulice, obec, psc, kontrola, '; '.join(notes)


def make_lv_row(unit: str, raw_name: str, address_text: str, extra_note: str = ''):
    name = raw_name.strip()
    company = is_company(name)

    poznamka_parts = []
    if extra_note:
        poznamka_parts.append(extra_note)

    ulice, obec, psc, addr_kontrola, addr_note = _address_to_fields(address_text)
    if addr_note:
        poznamka_parts.append(addr_note)

    if company:
        return {
            'Bytová jednotka': unit,
            'Oslovení': 'Vážení',
            'Jméno': '',
            'Příjmení': name,
            'Titul': '',
            'Ulice': ulice,
            'Obec': obec,
            'PSČ': psc,
            'Kontrola': 'ANO',
            'Poznámka': '; '.join(p for p in (['Právnická osoba / organizace'] + poznamka_parts) if p),
            'Původní adresa': address_text,
        }

    parsed = parse_person_name(name)
    gender, ambiguous = guess_gender(parsed['jmeno'], parsed['prijmeni'])
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
    if gender in ('M', 'F') and parsed['prijmeni']:
        vokativ_prijmeni, ok = vocative_surname(parsed['prijmeni'], is_woman)
        if ok:
            osloveni = f'{osloveni_zaklad} {vokativ_prijmeni}'
        else:
            osloveni = f'{osloveni_zaklad} {parsed["prijmeni"]}'
            declension_failed = True
    if declension_failed:
        poznamka_parts.append('Příjmení se nepodařilo sklonit do 5. pádu - ponecháno v 1. pádu')

    kontrola = ambiguous or addr_kontrola or declension_failed
    if not parsed['jmeno'] or not parsed['prijmeni']:
        kontrola = True
        poznamka_parts.append('Jméno nebo příjmení se nepodařilo jednoznačně rozdělit')

    return {
        'Bytová jednotka': unit,
        'Oslovení': osloveni,
        'Jméno': parsed['jmeno'],
        'Příjmení': parsed['prijmeni'],
        'Titul': parsed['titul'],
        'Ulice': ulice,
        'Obec': obec,
        'PSČ': psc,
        'Kontrola': 'ANO' if kontrola else 'NE',
        'Poznámka': '; '.join(p for p in poznamka_parts if p),
        'Původní adresa': address_text,
    }


def process_lv_pdf_to_rows(file):
    """
    Hlavní vstupní funkce pro tento typ dokumentu.
    Vrací (rows, debug_info: dict).
    """
    with pdfplumber.open(file) as pdf:
        full_text = '\n'.join((p.extract_text() or '') for p in pdf.pages)
        part_a_entries = extract_part_a_entries(pdf)

    id_to_address, name_to_address = build_id_address_maps(part_a_entries)

    part_b_text = extract_part_b_text(full_text)
    units = parse_part_b_units(part_b_text)

    rows = []
    unmatched = []
    sjm_flags = []

    for unit in units:
        if unit.get('typ_vyuziti', '').strip() != 'byt':
            continue
        for owner_line in unit.get('owner_lines', []):
            for owner_id, owner_name, is_sjm in parse_owner_line(owner_line):
                owner_name = owner_name.strip()
                if not owner_name:
                    continue
                address = None
                note = ''
                if owner_id and owner_id in id_to_address:
                    address = id_to_address[owner_id]
                else:
                    key = _normalize_name_key(owner_name)
                    if key in name_to_address:
                        address = name_to_address[key]
                        note = 'Adresa dohledána podle jména (identifikátor nenalezen)'
                    else:
                        address = ''
                        note = 'Adresa nenalezena v části A - zkontrolujte ručně'
                        unmatched.append((unit['unit'], owner_id, owner_name))

                rows.append(make_lv_row(unit['unit'], owner_name, address, note))
                sjm_flags.append(is_sjm)

    debug_info = {
        'full_text': full_text,
        'part_b_text': part_b_text,
        'part_a_entries_count': len(part_a_entries),
        'units_total': len(units),
        'units_byt': sum(1 for u in units if u.get('typ_vyuziti', '').strip() == 'byt'),
        'unmatched': unmatched,
        'sjm_flags': sjm_flags,
    }
    return rows, debug_info
