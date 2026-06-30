# -*- coding: utf-8 -*-
"""
app.py
Streamlit aplikace: PDF výpis z Nahlížení do katastru -> Excel
pro hromadnou korespondenci.

Spuštění:
    streamlit run app.py
"""

import io

import pandas as pd
import streamlit as st

from parser import process_pdf_to_rows, COLUMNS

st.set_page_config(
    page_title="Katastr → Excel pro hromadnou korespondenci",
    page_icon="📄",
    layout="wide",
)


def check_password() -> bool:
    """
    Jednoduchá ochrana heslem. Heslo se nastavuje v Streamlit "Secrets"
    (klíč APP_PASSWORD) - viz DEPLOY.md. Heslo se nikde neukládá do kódu
    ani do repozitáře.
    """

    def password_entered():
        correct = st.secrets.get("APP_PASSWORD", None)
        if correct is None:
            st.session_state["password_correct"] = True  # lokální vývoj bez secrets.toml
            return
        if st.session_state.get("password_input", "") == correct:
            st.session_state["password_correct"] = True
            st.session_state["password_input"] = ""
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.title("🔒 Přístup chráněn heslem")
    st.text_input(
        "Zadejte heslo", type="password", key="password_input",
        on_change=password_entered,
    )
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("Nesprávné heslo, zkuste to znovu.")
    return False


if not check_password():
    st.stop()

st.title("📄 Katastr nemovitostí → Excel pro hromadnou korespondenci")
st.write(
    "Nahrajte PDF výpis z **Nahlížení do katastru** (informace o stavbě / "
    "list vlastnictví) obsahující sekci „Vlastníci, jiní oprávnění“. "
    "Aplikace z něj vytvoří tabulku vlastníků připravenou pro hromadnou "
    "korespondenci."
)

if "rows" not in st.session_state:
    st.session_state["rows"] = None
if "full_text" not in st.session_state:
    st.session_state["full_text"] = ""
if "section_text" not in st.session_state:
    st.session_state["section_text"] = ""

uploaded_file = st.file_uploader("Nahrát PDF soubor", type=["pdf"])

col1, _ = st.columns([1, 4])
with col1:
    process_clicked = st.button(
        "🔄 Zpracovat", type="primary", disabled=uploaded_file is None
    )

if process_clicked and uploaded_file is not None:
    with st.spinner("Zpracovávám PDF…"):
        try:
            rows, full_text, section_text = process_pdf_to_rows(uploaded_file)
            st.session_state["rows"] = rows
            st.session_state["full_text"] = full_text
            st.session_state["section_text"] = section_text

            if not section_text:
                st.error(
                    "V PDF se nepodařilo najít sekci „Vlastníci, jiní "
                    "oprávnění“. Rozbalte níže „Debug“ a podívejte se na "
                    "extrahovaný text – možná je nadpis sekce v PDF napsán "
                    "jinak, nebo PDF obsahuje naskenovaný obrázek (bez "
                    "textové vrstvy)."
                )
            elif not rows:
                st.warning(
                    "Sekce „Vlastníci, jiní oprávnění“ byla nalezena, ale "
                    "nepodařilo se z ní rozpoznat žádného vlastníka. "
                    "Zkontrolujte extrahovaný text v sekci „Debug“ níže."
                )
            else:
                st.success(f"Hotovo – nalezeno {len(rows)} řádků vlastníků.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Chyba při zpracování PDF: {exc}")

rows = st.session_state.get("rows")

if rows:
    df = pd.DataFrame(rows, columns=COLUMNS)

    n_kontrola = (df["Kontrola"] == "ANO").sum()
    st.subheader("Náhled tabulky")
    st.caption(
        "⚠️ Tabulka níže má v pravém horním rohu (po najetí myší) svoji "
        "vlastní malou ikonku ke stažení – ta vždy stáhne soubor jako "
        "**.csv** (špatně se otevírá v Excelu). Pro správný Excel soubor "
        "použijte modré tlačítko **„⬇️ Stáhnout Excel (.xlsx)“** níže pod "
        "tabulkou."
    )
    if n_kontrola:
        st.info(
            f"⚠️ {n_kontrola} z {len(df)} řádků má Kontrola = ANO – "
            "doporučujeme je před odesláním ručně zkontrolovat (viz "
            "sloupec Poznámka). Tabulku níže můžete přímo opravit."
        )

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Kontrola": st.column_config.SelectboxColumn(
                "Kontrola", options=["ANO", "NE"]
            ),
        },
    )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        edited_df.to_excel(writer, index=False, sheet_name="Vlastnici")
        worksheet = writer.sheets["Vlastnici"]
        for column_cells in worksheet.columns:
            max_len = max(
                (len(str(cell.value)) for cell in column_cells if cell.value),
                default=0,
            )
            worksheet.column_dimensions[column_cells[0].column_letter].width = min(
                max(max_len + 2, 12), 40
            )
    buffer.seek(0)

    st.download_button(
        label="⬇️ Stáhnout Excel (.xlsx)",
        data=buffer,
        file_name="vlastnici_hromadna_korespondence.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    with st.expander("🔍 Debug – zkontrolovat extrahovaný text z PDF"):
        st.caption(
            "Pokud výsledek neodpovídá očekávání, podívejte se sem – podle "
            "tohoto textu lze snadno doladit pravidla v parser.py."
        )
        st.text_area(
            "Nalezená sekce „Vlastníci, jiní oprávnění“",
            st.session_state.get("section_text", ""),
            height=250,
        )
        st.text_area(
            "Celý text načtený z PDF",
            st.session_state.get("full_text", ""),
            height=250,
        )

elif uploaded_file is None:
    st.info("Nahrajte PDF soubor a klikněte na „Zpracovat“.")
else:
    st.info("Klikněte na „Zpracovat“ pro zpracování nahraného PDF.")
