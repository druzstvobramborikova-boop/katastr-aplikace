# Nasazení online zdarma (bez vlastního hostingu) – Streamlit Community Cloud

Tento návod appku zveřejní na adrese typu `https://nazev-projektu.streamlit.app`,
zdarma, bez potřeby Hostingeru nebo jiného serveru. Appka je chráněná
heslem (viz krok 4).

## Co budete potřebovat
- Účet na **GitHub** (zdarma) – [github.com/join](https://github.com/join)
- Účet na **Streamlit Community Cloud** (zdarma, přihlášení přes GitHub) –
  [share.streamlit.io](https://share.streamlit.io)

## Krok 1 – nahrát soubory na GitHub

1. Přihlaste se na [github.com](https://github.com).
2. Vpravo nahoře klikněte na **+** → **New repository**.
3. Pojmenujte ho např. `katastr-aplikace`.
4. Klikněte **Create repository**.
5. Nahrajte přes **"Add file" → "Upload files"** všechny soubory z
   projektu (včetně skryté složky `.streamlit` a souboru `.gitignore`).
6. Klikněte **Commit changes**.

## Krok 2 – propojit se Streamlit Community Cloud

1. Jděte na [share.streamlit.io](https://share.streamlit.io) a přihlaste
   se přes GitHub.
2. Klikněte **Create app** / **New app**.
3. Vyberte repozitář, branch `main`, hlavní soubor `app.py`.
4. Klikněte **Deploy**.

## Krok 3 – nastavit heslo (Secrets)

1. V detailu appky klikněte na **⋮** → **Settings** → záložka **Secrets**.
2. Vepište:
   ```toml
   APP_PASSWORD = "vase-tajne-heslo"
   ```
3. Klikněte **Save**.

## Krok 4 – appku zveřejnit (aby fungovala pro kohokoliv s heslem)

I když je GitHub repozitář **Public**, appka na Streamlit Cloud má
**svoje vlastní, oddělené nastavení "veřejná/neveřejná"**:

1. Otevřete appku, vpravo nahoře klikněte **"Share"**.
2. Klikněte **"Make this app public"** (pokud tam ta možnost je -
   výchozí stav appky z privátního i veřejného repozitáře bývá "jen
   pro vlastníka", dokud toto nezaškrtnete).
3. Bez tohoto kroku uvidí ostatní jen hlášku "You do not have access
   to this app or it does not exist" a budou muset appku vidět jako
   vy (přihlášeni na váš účet) - proto je tenhle krok důležitý.

## Repozitář Public vs Private

Doporučujeme mít repozitář **Public** - usnadňuje to Krok 4 výše a
appka i tak zůstává chráněná heslem (to je uložené jen v Secrets, ne
v repozitáři). Kód sám o sobě neobsahuje žádná osobní data - ta zůstávají
jen v paměti relace uživatele.

## Jak to funguje s daty (GDPR)

- Nahraná PDF a vygenerovaná Excel data zůstávají pouze v paměti
  relace (session) a nikam se trvale neukládají.
- Appka na free tieru "usne", pokud na ni 12 hodin nikdo nezavítá -
  při dalším otevření stačí kliknout na tlačítko "Yes, get this app
  back up!" a appka se do minuty znovu nastartuje, žádná data ani
  nastavení se neztratí.

## Pokud se nasazení nepovede

V detailu appky klikněte na **"Manage app"** → uvidíte log s chybovou
hláškou.
