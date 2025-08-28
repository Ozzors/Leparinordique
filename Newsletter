# app.py
# Streamlit newsletter app (FR/EN) with Google Sheets backend
# Author: ChatGPT for Oswaldo
# -----------------------------------------------------------------------------
import os
from datetime import datetime
from typing import Dict

import pandas as pd
import streamlit as st

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception as e:
    st.error("Falta instalar dependencias: gspread y google-auth. Ejecuta: pip install gspread google-auth")
    raise

# ----------------------------- CONFIG & THEME ---------------------------------
st.set_page_config(
    page_title="Le Pari Nordique – Newsletter",
    page_icon="🏅",
    layout="wide",
)

PRIMARY = "#0EA5E9"  # tailwind sky-500
ACCENT = "#F59E0B"   # tailwind amber-500

CUSTOM_CSS = f"""
<style>
:root {{ --primary: {PRIMARY}; --accent: {ACCENT}; }}
.block-container {{ padding-top: 2rem; }}
h1, h2, h3 {{ letter-spacing: .2px; }}
.kicker {{ color: var(--primary); font-weight: 600; text-transform: uppercase; font-size: .85rem; }}
.edition-card {{ border: 1px solid rgba(0,0,0,.06); border-radius: 16px; padding: 1rem 1.25rem; box-shadow: 0 2px 12px rgba(0,0,0,.04); }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: .75rem; background: rgba(14,165,233,.1); color: var(--primary); margin-right: .5rem; }}
.meta {{ color: #6b7280; font-size: .9rem; }}
.lang-switch .stRadio > label {{ gap: .5rem; }}
.codebox {{ background: #0b1020; color: #e5e7eb; padding: .75rem 1rem; border-radius: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .85rem; }}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ----------------------------- I18N -------------------------------------------
I18N: Dict[str, Dict[str, str]] = {
    "en": {
        "app_title": "Le Pari Nordique",
        "subtitle": "Sports betting insights — clean, bilingual, and fast",
        "latest": "Latest Edition",
        "archive": "Archive",
        "stats": "Performance",
        "refresh": "Refresh",
        "last_sync": "Last sync",
        "empty": "No editions published yet in this language.",
        "search": "Search in titles...",
        "published": "Published",
    },
    "fr": {
        "app_title": "Le Pari Nordique",
        "subtitle": "Pari sportifs — clair, bilingue et rapide",
        "latest": "Dernière édition",
        "archive": "Archives",
        "stats": "Performance",
        "refresh": "Rafraîchir",
        "last_sync": "Dernière synchro",
        "empty": "Aucune édition publiée pour cette langue.",
        "search": "Rechercher dans les titres...",
        "published": "Publié",
    },
}

# ----------------------------- SECRETS & GSPREAD ------------------------------
# Expected secrets:
# st.secrets["gcp_service_account"] -> dict with service account JSON
# st.secrets["newsletter_sheet_id"]  -> Google Sheet ID (string)

@st.cache_resource(show_spinner=False)
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    info = st.secrets.get("gcp_service_account", None)
    if not info:
        st.stop()
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def load_editions(sheet_id: str) -> pd.DataFrame:
    gc = get_gspread_client()
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet("editions")
    rows = ws.get_all_records()
    df = pd.DataFrame(rows)
    # Normalize expected columns
    expected = ["edition_id", "date", "language", "title", "content_md", "published"]
    for col in expected:
        if col not in df.columns:
            df[col] = None
    # Parse date
    if not df.empty:
        try:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        except Exception:
            pass
        # Ensure boolean for published
        df["published"] = df["published"].astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y", "oui"])    
        # Sort latest first
        df = df.sort_values("date", ascending=False, na_position="last")
    return df

# ----------------------------- SIDEBAR ----------------------------------------
with st.sidebar:
    st.markdown(f"<div class='kicker'>Newsletter</div>", unsafe_allow_html=True)
    st.title("Le Pari Nordique 🏅")
    st.caption("Bilingual sports betting newsletter")

    lang = st.radio(
        "Language / Langue",
        options=["fr", "en"],
        format_func=lambda x: "Français" if x == "fr" else "English",
        horizontal=False,
        key="lang",
    )

    sheet_id = st.secrets.get("newsletter_sheet_id", "")
    if not sheet_id:
        st.warning("Configura st.secrets['newsletter_sheet_id'] para conectar tu Google Sheet.")

    if st.button(I18N[lang]["refresh"], use_container_width=True):
        load_editions.clear()

# ----------------------------- HEADER -----------------------------------------
st.markdown(
    f"""
    <div>
      <div class='kicker'>{{I18N}}</div>
      <h1 style='margin-bottom:.25rem'>{I18N[lang]['app_title']}</h1>
      <p class='meta'>{I18N[lang]['subtitle']}</p>
    </div>
    """.replace("{{I18N}}", "FR / EN"),
    unsafe_allow_html=True,
)

# ----------------------------- DATA LOAD --------------------------------------
if sheet_id:
    df = load_editions(sheet_id)
else:
    df = pd.DataFrame()

st.caption(f"{I18N[lang]['last_sync']}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ----------------------------- LATEST -----------------------------------------
st.subheader(I18N[lang]["latest"])
if df.empty:
    st.info(I18N[lang]["empty"])  # nothing to show
else:
    dfx = df[(df["published"] == True) & (df["language"].str.lower() == lang)]
    if dfx.empty:
        st.info(I18N[lang]["empty"]) 
    else:
        latest = dfx.iloc[0]
        with st.container(border=True):
            c1, c2 = st.columns([3,1])
            with c1:
                st.markdown(f"<span class='badge'>{latest['language'].upper()}</span>", unsafe_allow_html=True)
                st.markdown(f"## {latest['title']}")
                if pd.notna(latest.get("date")):
                    st.markdown(f"<div class='meta'>{latest['date'].strftime('%Y-%m-%d')}</div>", unsafe_allow_html=True)
                st.markdown(latest.get("content_md", ""))
            with c2:
                st.metric("ID", str(latest.get("edition_id", "-")))
                st.metric(I18N[lang]["published"], "✅")

# ----------------------------- ARCHIVE ----------------------------------------
st.divider()
st.subheader(I18N[lang]["archive"])

if not df.empty:
    dfa = df[(df["published"] == True) & (df["language"].str.lower() == lang)].copy()
    query = st.text_input(I18N[lang]["search"], value="", placeholder="e.g., NHL, week 3, parlays")
    if query:
        q = query.lower().strip()
        dfa = dfa[dfa["title"].astype(str).str.lower().str.contains(q) | dfa["content_md"].astype(str).str.lower().str.contains(q)]

    if dfa.empty:
        st.info(I18N[lang]["empty"]) 
    else:
        for _, row in dfa.iterrows():
            with st.expander(f"{row['date'].strftime('%Y-%m-%d') if pd.notna(row['date']) else ''} — {row['title']}"):
                st.markdown(f"<span class='badge'>{row['language'].upper()}</span>", unsafe_allow_html=True)
                st.markdown(row.get("content_md", ""))

# ----------------------------- OPTIONAL: SIMPLE STATS -------------------------
# Minimal placeholder — later we can compute accuracy, ROI, etc., by edition.
st.divider()
st.subheader(I18N[lang]["stats"])
st.write(
    "Placeholder para métricas (aciertos por liga, yield, ROI). Podemos conectar otra hoja 'picks' para calcularlo."
)

# ----------------------------- FOOTER -----------------------------------------
st.caption("© "+str(datetime.now().year)+" Le Pari Nordique — Built with Streamlit")
