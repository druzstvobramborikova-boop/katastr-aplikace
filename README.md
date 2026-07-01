# Katastr → Excel pro hromadnou korespondenci

Jednoduchá Streamlit aplikace, která z PDF výpisu z **Nahlížení do katastru
nemovitostí** (informace o stavbě / list vlastnictví) vytáhne sekci
„Vlastníci, jiní oprávnění“ a vyexportuje ji do Excelu připraveného pro
hromadnou korespondenci.

## Soubory

| Soubor | Popis |
|---|---|
| `app.py` | Streamlit aplikace (UI – nahrání PDF, tlačítko Zpracovat, náhled, download) |
| `parser.py` | Logika pro jednodušší PDF typu "Informace o stavbě/pozemku" (sekce „Vlastníci, jiní oprávnění“) |
| `lv_parser.py` | Logika pro kompletní "VÝPIS Z KATASTRU NEMOVITOSTÍ" (list vlastnictví s částí A a B, výstup po bytových jednotkách) |
| `requirements.txt` | Seznam potřebných knihoven |

## Dva podporované typy PDF

Aplikace automaticky pozná, jaký typ PDF jste nahráli:

**1) Informace o stavbě / o pozemku** - jednodušší výpis se sekcí
„Vlastníci, jiní oprávnění“. Výstupní sloupce: Oslovení, Titul, Jméno,
Příjmení / Název, Ulice, Číslo domu, PSČ, Obec, Kontrola, Poznámka,
Původní adresa.

**2) Kompletní výpis z katastru (list vlastnictví)** - má část A
(seznam vlastníků s rodnými čísly/IČO a adresami) a část B (seznam
bytových jednotek a jejich vlastníků). Aplikace tyto dvě části spojí
podle rodného čísla / IČO a vytvoří jeden řádek pro každého vlastníka
KAŽDÉ bytové jednotky (pokud má jednotka víc vlastníků, je pro ně víc
řádků). Zohledňují se jen jednotky se způsobem využití „byt“ (společné
/ nebytové prostory typu sklepy, ateliéry apod. se do výstupu
nezahrnují). Výstupní sloupce: Bytová jednotka, Oslovení, Jméno,
Příjmení, Titul, Ulice, Obec, PSČ, Kontrola, Poznámka, Původní adresa.

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

## Ulice a městská část

Sloupec **Ulice** obsahuje jen ulici a číslo domu (např. „Kyselova
1185/2“) - městská část / část obce (např. „Kobylisy“) se do něj
NEzahrnuje, protože pro hromadnou korespondenci se nepoužívá. Pokud je
v adrese uvedená, najdete ji jen v Poznámce pro informaci.

Pokud adresa naopak ŽÁDNOU městskou část neuvádí (např. „Milčice 32,
38801 Blatná“), nejde spolehlivě poznat, jestli je první část adresy
skutečná ulice, nebo jde o samostatnou vesnici/obec zapsanou bez
ulice. Takové řádky se proto vždy označí **Kontrola = ANO** s
poznámkou „Nejisté, zda je skutečná ulice…“ - očekávejte tedy u adres
z menších obcí vyšší podíl řádků ke kontrole, to je záměr, ne chyba.

## Oslovení v 5. pádu (vokativ)

Sloupec **Oslovení** obsahuje rovnou celý pozdrav se skloňovaným
příjmením, např. „Vážený pane Nováku" nebo „Vážená paní Fialová"
(u žen na „-ová" se v 5. pádu příjmení nemění). Skloňování zajišťuje
knihovna [`vokativ`](https://pypi.org/project/vokativ/) (autor Michal
Danilák), která má dle statistik četnosti jmen v ČR přesnost cca 99,7 %.

**Důležité upozornění:** Automatické skloňování češtiny nikdy nebude
100% přesné, zejména u méně obvyklých nebo cizokrajných příjmení.
Pokud se jméno nepodaří sklonit (knihovna to sama pozná), zůstane
v Oslovení příjmení v 1. pádu a řádek dostane Kontrola = ANO
s poznámkou „Příjmení se nepodařilo sklonit do 5. pádu". I u úspěšně
skloněných jmen ale doporučujeme před rozesláním korespondence
namátkově pár řádků zkontrolovat - u některých neobvyklých jmen může
být tvar sporný i pro rodilého mluvčího.

Pokud knihovna `vokativ` není nainstalovaná (např. při lokálním testu
bez internetu), aplikace na to nespadne - jen ponechá příjmení v 1.
pádu u všech řádků a označí je Kontrola = ANO.

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
