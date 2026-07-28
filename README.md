# Katastr → Excel pro hromadnou korespondenci

Jednoduchá Streamlit aplikace, která z PDF výpisu z katastru nemovitostí
vytáhne seznam vlastníků a vyexportuje ho do Excelu připraveného pro
hromadnou korespondenci.

## Soubory

| Soubor | Popis |
|---|---|
| `app.py` | Streamlit aplikace (UI – nahrání PDF, tlačítko Zpracovat, náhled, download) |
| `parser.py` | Logika pro jednodušší PDF typu "Informace o stavbě/pozemku" (sekce „Vlastníci, jiní oprávnění“) |
| `lv_parser.py` | Logika pro kompletní "VÝPIS Z KATASTRU NEMOVITOSTÍ" (list vlastnictví s částí A a B, výstup po bytových jednotkách) |
| `couple_merge.py` | Rozpoznání manželských párů na stejné adrese (pro sloučení korespondence) |
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

## Více PDF najednou

Do aplikace jde nahrát i **víc PDF souborů najednou** (i namíchaně oba
typy dokumentů). Výsledek se vždy spojí do **jednoho** staženého Excel
souboru:

- Pokud jsou všechny nahrané soubory stejného typu, budou spojené do
  jednoho listu.
- Pokud nahrajete oba typy dokumentů zároveň, výsledný sešit bude mít
  **dva listy** ("Vlastnici" a "Jednotky").
- Při nahrání víc souborů se navíc přidá sloupec **„Zdrojový soubor“**,
  aby šlo poznat, odkud který řádek pochází. Při nahrání jediného
  souboru se tento sloupec nepřidává (aby tabulka zůstala přehlednější).
- Rozpoznávání manželských párů (viz níže) se dělá vždy jen v rámci
  jednoho zdrojového souboru, nikdy napříč různými PDF.

## Manželé na stejné adrese - jeden dopis místo dvou

Aplikace do tabulky automaticky přidá dva sloupce:

- **Pár (manželé)** - ANO, pokud aplikace na stejné adrese (u
  bytových jednotek na stejné jednotce) našla dvojici opačného
  pohlaví se shodným kořenem příjmení (zvládá i nepravidelné tvary
  jako Novotný/Novotná, Svoboda/Svobodová, ne jen prosté „-ová“).
- **Odeslat dopis** - ANO / „NE (viz manžel/manželka výše)“. U
  rozpoznaných párů se u DRUHÉHO z dvojice nastaví na NE, takže při
  hromadné korespondenci stačí filtrovat sloupec „Odeslat dopis“ = ANO
  a pár dostane jen jeden dopis.

I zde platí, že jde o automatické rozpoznávání - u neobvyklých
příjmení doporučujeme páry před odesláním zkontrolovat (sloupec je
přímo v náhledu editovatelný).

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

## Instalace a spuštění na Windows

1. **Nainstalujte Python** (pokud ho ještě nemáte) – stáhněte z
   [python.org/downloads](https://www.python.org/downloads/) a při instalaci
   zaškrtněte „Add python.exe to PATH“.

2. **Otevřete PowerShell nebo Příkazový řádek** ve složce s těmito soubory.

3. **Vytvořte virtuální prostředí:**
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```

4. **Nainstalujte potřebné knihovny:**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Spusťte aplikaci:**
   ```powershell
   streamlit run app.py
   ```
   Po spuštění se automaticky otevře prohlížeč na adrese
   `http://localhost:8501`.

6. **Příště** stačí ve složce projektu spustit jen kroky 3 (aktivace
   prostředí, `venv\Scripts\activate`) a 5 (`streamlit run app.py`).

## Jak aplikaci používat

1. Nahrajte jedno nebo víc PDF přes „Nahrát PDF soubor(y)“.
2. Klikněte na „🔄 Zpracovat“.
3. Zkontrolujte náhled tabulky (u smíšených typů dokumentů budou dvě
   záložky). Řádky se sloupcem **Kontrola = ANO** doporučujeme ručně
   zkontrolovat. Tabulka je editovatelná přímo v náhledu.
4. Klikněte na „⬇️ Stáhnout Excel (.xlsx)“ (POZOR: nepoužívejte malou
   ikonku pro stažení přímo nad náhledovou tabulkou – ta stahuje jako
   .csv, což se v Excelu neotevře správně rozdělené do sloupců).

## Důležitá omezení (čtěte prosím)

Formát PDF z katastru se může mírně lišit (různé verze generátoru,
regionální odlišnosti) a extrakce textu z PDF může u některých
neobvyklých rozvržení selhat. Parser proto pracuje s heuristikami, ne
s přesnou znalostí formátu. Konkrétně:

- **Naskenované PDF (obrázek bez textové vrstvy)** nebude fungovat
  vůbec – text se z něj nedá přečíst.
- **Rozdělení ulice vs. části obce** nelze bez databáze obcí spolehlivě
  poznat vždy – viz sekci výše.
- **Odhad pohlaví** a **skloňování do 5. pádu** jsou založené na
  koncovkách jmen a mohou se u neobvyklých nebo cizích jmen zmýlit –
  proto existuje sloupec Kontrola.
- Pokud parser u vašich konkrétních PDF něco systematicky špatně
  rozpozná, podívejte se do Debug náhledu extrahovaného textu a podle
  něj upravte regulární výrazy v `parser.py` / `lv_parser.py`.

## Spuštění bez instalace Pythonu pokaždé znovu

Vytvořte si ve složce projektu soubor `spustit.bat`:

```bat
@echo off
call venv\Scripts\activate
streamlit run app.py
pause
```

Pak stačí na něj dvakrát kliknout.
