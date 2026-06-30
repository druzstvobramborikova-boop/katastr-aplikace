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
3. Pojmenujte ho např. `katastr-aplikace`. Zvolte **Private** (doporučeno,
   ať kód nevidí kdokoliv) nebo Public – pro Streamlit Cloud free tier
   funguje obojí.
4. Klikněte **Create repository**.
5. V novém repozitáři klikněte na **"uploading an existing file"** (nebo
   **Add file → Upload files**).
6. Nahrajte tyto soubory ze složky, kterou jste dostali ode mě:
   - `app.py`
   - `parser.py`
   - `requirements.txt`
   - `.gitignore`
   - (soubor `.streamlit/secrets.toml.example` nahrát NEMUSÍTE, je jen
     pro inspiraci - skutečné heslo se nastavuje přímo ve Streamlit Cloud,
     viz krok 4)
7. Dole klikněte **Commit changes**.

## Krok 2 – propojit se Streamlit Community Cloud

1. Jděte na [share.streamlit.io](https://share.streamlit.io) a přihlaste
   se přes GitHub (tlačítko "Continue with GitHub").
2. Klikněte **Create app** / **New app**.
3. Vyberte:
   - **Repository:** `vase-jmeno/katastr-aplikace`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Klikněte **Deploy**.

Appka se začne instalovat (potrvá ~1–3 minuty, instalují se knihovny z
`requirements.txt`).

## Krok 3 – nastavit heslo (Secrets)

1. V detailu vaší appky na Streamlit Cloud klikněte na **⋮ (tři tečky)**
   vpravo nahoře → **Settings** → záložka **Secrets**.
2. Vepište:
   ```toml
   APP_PASSWORD = "vase-tajne-heslo"
   ```
   (heslo si zvolte vlastní, klidně delší frázi).
3. Klikněte **Save**. Appka se sama restartuje s novým nastavením.

## Krok 4 – vyzkoušet

1. Otevřete URL appky (najdete ji nahoře, tvar
   `https://nahodny-nebo-vami-zvoleny-nazev.streamlit.app`).
2. Appka by měla nejdřív zobrazit obrazovku **"🔒 Přístup chráněn heslem"**.
3. Zadejte heslo z kroku 3 → mělo by vás to pustit dál do appky.

## Jak to funguje s daty (GDPR)

- Streamlit Community Cloud appku spouští jako běžný proces – nahraná
  PDF a vygenerovaná Excel data zůstávají pouze v paměti relace (tak, jak
  je to napsané v `app.py`) a nikam se trvale neukládají.
- Pozor: appka na free tieru "usíná" po cca týdnu neaktivity (probudí se
  sama při dalším otevření, jen to chvíli trvá) a při dlouhé nečinnosti
  se relace (session) může restartovat - to ale neznamená únik dat, jen
  je potřeba znovu zadat heslo a nahrát PDF.
- I tak doporučuji repozitář na GitHubu nechat **Private**, a appku
  nesdílet veřejně (jen lidem, kteří mají znát heslo).

## Až budete chtít appku přesunout na vlastní doménu

Tenhle postup je ideální na vyzkoušení. Pokud appka funguje k vaší
spokojenosti a budete chtít, aby běžela přímo na `martinavlckova.cz/katastr`,
budete potřebovat Hostinger VPS (ne sdílený hosting) - dejte vědět, připravím
Dockerfile a návod na nasazení tam, včetně nastavení cesty `/katastr` a
zabezpečení i na úrovni serveru.

## Pokud se nasazení nepovede

Nejčastější problém bývá chyba v `requirements.txt` nebo nekompatibilní
verze knihovny. V detailu appky na Streamlit Cloud klikněte na **"Manage
app"** vlevo dole → uvidíte log s chybovou hláškou. Tu mi klidně pošlete,
pomůžu to doladit.
