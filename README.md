# Katastr → Excel pro hromadnou korespondenci

Jednoduchá Streamlit aplikace, která z PDF výpisu z **Nahlížení do katastru
nemovitostí** (informace o stavbě / list vlastnictví) vytáhne sekci
„Vlastníci, jiní oprávnění“ a vyexportuje ji do Excelu připraveného pro
hromadnou korespondenci.

## Soubory

| Soubor | Popis |
|---|---|
| `app.py` | Streamlit aplikace (UI – nahrání PDF, tlačítko Zpracovat, náhled, download) |
| `parser.py` | Veškerá logika čtení PDF a parsování jmen/adres |
| `requirements.txt` | Seznam potřebných knihoven |

## Instalace a spuštění na Windows

1. **Nainstalujte Python** (pokud ho ještě nemáte) – stáhněte z
   [python.org/downloads](https://www.python.org/downloads/) a při instalaci
   zaškrtněte „Add python.exe to PATH“.

2. **Otevřete PowerShell nebo Příkazový řádek** ve složce s těmito soubory
   (např. klikněte pravým tlačítkem ve složce → „Otevřít v terminálu“).

3. **Vytvořte virtuální prostředí** (doporučeno, ať se knihovny nemíchají
   s ostatními projekty):
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```
   Po aktivaci by se na začátku řádku mělo objevit `(venv)`.

4. **Nainstalujte potřebné knihovny:**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Spusťte aplikaci:**
   ```powershell
   streamlit run app.py
   ```
   Po spuštění se automaticky otevře prohlížeč na adrese
   `http://localhost:8501`. Pokud se neotevře sám, otevřete tuto adresu
   ručně.

6. **Příště** stačí ve složce projektu spustit jen kroky 3 (aktivace
   prostředí, `venv\Scripts\activate`) a 5 (`streamlit run app.py`).

## Jak aplikaci používat

1. Nahrajte PDF přes „Nahrát PDF soubor“.
2. Klikněte na „🔄 Zpracovat“.
3. Zkontrolujte náhled tabulky – řádky se sloupcem **Kontrola = ANO**
   doporučujeme ručně zkontrolovat (důvod je vždy uveden ve sloupci
   **Poznámka**). Tabulka je editovatelná přímo v náhledu, takže můžete
   chyby rovnou opravit.
4. Klikněte na „⬇️ Stáhnout Excel (.xlsx)“.

Pokud se sekce vlastníků nenajde nebo se rozpozná špatně, rozbalte v
aplikaci sekci „🔍 Debug – zkontrolovat extrahovaný text z PDF“ – uvidíte
přesně, jaký text pdfplumber z PDF přečetl, a podle toho se dá snadno
doladit logika v `parser.py`.

## Jak nástroj funguje (stručně)

- `pdfplumber` přečte text ze všech stránek PDF.
- V textu se vyhledá nadpis „Vlastníci, jiní oprávnění“ a vyřízne se text
  až po další nadpis (např. „Jiné zápisy“, „Omezení vlastnického práva“…).
- Tento blok textu se řádek po řádku rozdělí na jednotlivé vlastníky:
  řádek **bez číslice** = jméno (osoby/firmy), řádek **s číslicí** =
  adresa. Řádky jako „Podíl: …“, „Jednotka …“, „IČO …“ se z adresy
  vyřadí a uloží do poznámky.
- U „SJM Příjmení1 Jméno1 a Příjmení2 Jméno2“ se vytvoří dva řádky.
  Pokud po SJM řádku následuje jeden řádek adresy, použije se pro oba
  manžele. Pokud následují dva řádky adresy, použije se každému manželovi
  jeho vlastní.
- Adresa se rozdělí na ulici, číslo domu, PSČ a obec podle posledního
  úseku s pětimístným PSČ.
- Tituly (Ing., Mgr., MUDr., …) se odstraní ze jména/příjmení a uloží do
  sloupce Titul.
- Oslovení se odhaduje podle koncovky křestního jména a příjmení
  (typicky „-ová“ = paní, „-a“/„-ie“ na konci jména = paní, jinak pán).
- Právnické osoby (s.r.o., a.s., obec, kraj, spolek, …) se nechají jako
  jeden řádek se jménem v sloupci „Příjmení / Název“, osloveni „Vážení“,
  Kontrola = ANO.
- Na konci se odstraní přesné duplicity (stejný titul, jméno, příjmení a
  adresa).

## Důležitá omezení (čtěte prosím)

Formát PDF z Nahlížení do katastru se může mírně lišit (LV, informace o
pozemku/stavbě, různé verze generátoru) a samotná extrakce textu z PDF
(`pdfplumber`) může ztratit informace o sloupcích/odsazení. Parser proto
pracuje s heuristikami, ne s přesnou znalostí formátu. Konkrétně:

- **Naskenované PDF (obrázek bez textové vrstvy)** nebude fungovat vůbec –
  text se z něj nedá přečíst. Aplikace na to upozorní (sekce se nenajde).
- **Rozdělení ulice vs. části obce** (např. „Krásné 186, 353 01 Tři
  Sekery“, kde „Krásné“ může být místní část, ne ulice) nelze bez databáze
  obcí spolehlivě poznat – takové případy doporučujeme vždy zkontrolovat.
- **Odhad pohlaví** je založen na koncovkách jmen a může se u neobvyklých
  nebo cizích jmen zmýlit – proto existuje sloupec Kontrola.
- Pokud parser u vašich konkrétních PDF něco systematicky špatně rozpozná,
  podívejte se do Debug náhledu extrahovaného textu a podle něj upravte
  regulární výrazy v `parser.py` (jsou okomentované) – případně mi pošlete
  anonymizovaný úryvek textu (bez osobních údajů) a pravidla doladím.

## Spuštění bez instalace Pythonu pokaždé znovu

Pokud chcete aplikaci spouštět jedním kliknutím, můžete si ve složce
projektu vytvořit soubor `spustit.bat` s tímto obsahem:

```bat
@echo off
call venv\Scripts\activate
streamlit run app.py
pause
```

Pak stačí na něj dvakrát kliknout.
