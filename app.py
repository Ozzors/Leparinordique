# Le Pari Nordique — Streamlit app with local editor + GitHub-backed CSV storage
# Flexible logo URL: accepts .png or .jpg from GitHub

import os
import io
import time
from datetime import datetime, date
from typing import Optional, Tuple

import pandas as pd
import requests
import streamlit as st
import base64

# ----------------------------- PAGE CONFIG & THEME ---------------------------
st.set_page_config(page_title="Le Pari Nordique – Newsletter (Admin)", page_icon="🏅", layout="wide")

PRIMARY = "#0EA5E9"
ACCENT = "#F59E0B"
CUSTOM_CSS = f"""
<style>
:root {{ --primary: {PRIMARY}; --accent: {ACCENT}; }}
.block-container {{ padding-top: 2rem; }}
.kicker {{ color: var(--primary); font-weight: 600; text-transform: uppercase; font-size: .85rem; }}
.edition-card {{ border: 1px solid rgba(0,0,0,.06); border-radius: 16px; padding: 1rem 1.25rem; box-shadow: 0 2px 12px rgba(0,0,0,.04); }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: .75rem; background: rgba(14,165,233,.1); color: var(--primary); margin-right: .5rem; }}
.meta {{ color: #6b7280; font-size: .9rem; }}
.codebox {{ background: #0b1020; color: #e5e7eb; padding: .75rem 1rem; border-radius: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .85rem; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ----------------------------- FLEXIBLE LOGO URL -----------------------------
GITHUB_LOGO_DIR = "https://raw.githubusercontent.com/Ozzors/Leparinordique/dfab971279f8e3ea44ef2fe3faf3b6caf02fc8e3/assets/"
def get_logo_url():
    possible_names = ["logo.png", "logo.jpg", "IMG-20250903-WA0001.jpg", "IMG-20250903-WA0001.png"]
    for name in possible_names:
        url = GITHUB_LOGO_DIR + name
        r = requests.head(url)
        if r.status_code == 200:
            return url
    return None

LOGO_URL = get_logo_url()

# ----------------------------- I18N -------------------------------------------
I18N = {
    "en": {
        "app_title": "Le Pari Nordique",
        "subtitle": "Sports betting insights — admin editor",
        "latest": "🏆 Latest Edition",
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
        "subtitle": "Pari sportifs — admin",
        "latest": "🏆 Dernière édition",
        "archive": "Archives",
        "stats": "Performance",
        "refresh": "Rafraîchir",
        "last_sync": "Dernière synchro",
        "empty": "Aucune édition publiée pour cette langue.",
        "search": "Rechercher dans les titres...",
        "published": "Publié",
    },
}

# ----------------------------- CONFIG: GitHub / Local -------------------------
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "").strip()
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "").strip()
GITHUB_PATH = st.secrets.get("GITHUB_PATH", "editions.csv").strip()
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main").strip()
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "").strip()

LOCAL_CSV = "editions.csv"

# ----------------------------- SESSION STATE (admin persist + prompt) --------
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False
if "show_admin_login" not in st.session_state:
    st.session_state["show_admin_login"] = False
if "admin_ask_stay" not in st.session_state:
    st.session_state["admin_ask_stay"] = False

# ----------------------------- GITHUB HELPERS --------------------------------
def _gh_headers(token: str) -> dict:
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

def github_get_file(repo: str, path: str, token: str, branch: str = "main") -> Tuple[Optional[bytes], Optional[str]]:
    if not (repo and token):
        return None, None
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    try:
        r = requests.get(url, headers=_gh_headers(token), params={"ref": branch}, timeout=20)
    except Exception as e:
        st.error(f"Error talking to GitHub: {e}")
        return None, None
    if r.status_code == 200:
        j = r.json()
        content = base64.b64decode(j["content"].encode())
        return content, j.get("sha")
    elif r.status_code == 404:
        return None, None
    else:
        st.error(f"GitHub API error: {r.status_code} — {r.text}")
        return None, None

def github_put_file(repo: str, path: str, token: str, content_bytes: bytes, message: str, sha: Optional[str] = None, branch: str = "main") -> Optional[dict]:
    if not (repo and token):
        st.error("GitHub is not configured (missing token or repo).")
        return None
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    try:
        r = requests.put(url, headers=_gh_headers(token), json=payload, timeout=30)
    except Exception as e:
        st.error(f"Error talking to GitHub: {e}")
        return None
    if r.status_code in (200, 201):
        return r.json()
    else:
        st.error(f"Failed to write file to GitHub: {r.status_code} — {r.text}")
        return None

# ----------------------------- DATA LOADING / SAVING -------------------------
@st.cache_data(ttl=30)
def load_editions_from_github() -> Tuple[pd.DataFrame, Optional[str]]:
    if not (GITHUB_TOKEN and GITHUB_REPO):
        return pd.DataFrame(), None
    content, sha = github_get_file(GITHUB_REPO, GITHUB_PATH, GITHUB_TOKEN, branch=GITHUB_BRANCH)
    if content is None:
        return pd.DataFrame(), None
    try:
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    except Exception as e:
        st.error(f"Failed to parse CSV from GitHub: {e}")
        return pd.DataFrame(), sha
    expected = ["edition_id", "date", "language", "title", "content_md", "published"]
    for col in expected:
        if col not in df.columns:
            df[col] = None
    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    except Exception:
        pass
    df["published"] = df["published"].astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y", "oui"])
    df = df.sort_values(["date", "edition_id"], ascending=[False, False], na_position="last").reset_index(drop=True)
    return df, sha

def load_editions_local() -> pd.DataFrame:
    if os.path.exists(LOCAL_CSV):
        try:
            df = pd.read_csv(LOCAL_CSV)
            for col in ["edition_id", "date", "language", "title", "content_md", "published"]:
                if col not in df.columns:
                    df[col] = None
            try:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
            except Exception:
                pass
            df["published"] = df["published"].astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y", "oui"])
            return df.sort_values("date", ascending=False, na_position="last").reset_index(drop=True)
        except Exception as e:
            st.error(f"Failed to read local CSV: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

def save_editions_to_github(df: pd.DataFrame, prev_sha: Optional[str]) -> Optional[dict]:
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    message = f"Update editions.csv — {datetime.utcnow().isoformat()}"
    return github_put_file(GITHUB_REPO, GITHUB_PATH, GITHUB_TOKEN, csv_bytes, message, sha=prev_sha, branch=GITHUB_BRANCH)

def save_editions_local(df: pd.DataFrame):
    df.to_csv(LOCAL_CSV, index=False)

# ----------------------------- SIDEBAR --------------------------------------
with st.sidebar:
    if LOGO_URL:
        st.image(LOGO_URL, width=150)
    st.markdown("<div class='kicker'>Newsletter</div>", unsafe_allow_html=True)
    st.title("Le Pari Nordique 🏅")
    #st.caption("Admin editor — saves to GitHub or local CSV")

    lang = st.radio(
        "Language / Langue",
        options=["fr", "en"],
        index=1,
        format_func=lambda x: "Français" if x == "fr" else "English",
        key="lang_radio"
    )

    if st.button("Refresh data", use_container_width=True, key="refresh_button"):
        load_editions_from_github.clear()

    if st.button("⚙️", key="admin_icon"):
        st.session_state["show_admin_login"] = not st.session_state["show_admin_login"]

    if st.session_state["show_admin_login"] and not st.session_state["is_admin"]:
        with st.expander("Admin login", expanded=True):
            st.text_input("Enter admin password:", type="password", key="pw_input")
            if st.button("Login", key="login_btn"):
                if ADMIN_PASSWORD and st.session_state.get("pw_input") == ADMIN_PASSWORD:
                    st.session_state["is_admin"] = True
                    st.session_state["show_admin_login"] = False
                    st.success("Admin mode enabled")
                    st.rerun()
                else:
                    st.error("Wrong password")


# ----------------------------- MAIN LOGO + BILINGUAL BANNER ---------------------
if LOGO_URL:
    # Logo centrado y más grande
    st.markdown(
        f"""
        <div style='text-align: center; margin-bottom: 10px;'>
            <img src="{LOGO_URL}" width="325" style="border-radius:12px;" />
        </div>
        """,
        unsafe_allow_html=True
    )

    # Banner a la derecha, subido un poco
    st.markdown(
        """
        <div style='display:flex; justify-content:flex-end; margin-bottom:15px; margin-top:-150px;'>
            <div style="display:flex; align-items:center; justify-content:center; padding:10px 16px; border-radius:12px; font-size:16px; font-weight:bold; background: linear-gradient(90deg, #1e3c72, #2a5298); color: #FFD700; box-shadow: 0 3px 5px rgba(0,0,0,0.2); text-align:center;">
                📅 Publishes twice a week / Publié deux fois par semaine ⚽🔥
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Contact debajo
    st.markdown(
        """
        <div style='text-align: center; font-size:0.9rem; color:#6b7280; margin-bottom:1rem;'>
            Contact: <a href='mailto:Leparinordique@parisportifquebecc.wine' style='color:#6b7280;'>Leparinordique@parisportifquebecc.wine</a>
        </div>
        """,
        unsafe_allow_html=True
    )
# ----------------------------- LOAD DATA ------------------------------------
if GITHUB_TOKEN and GITHUB_REPO:
    df, gh_sha = load_editions_from_github()
    source = f"GitHub: {GITHUB_REPO}/{GITHUB_PATH} (branch: {GITHUB_BRANCH})"
else:
    df = load_editions_local()
    gh_sha = None
    source = f"Local file: {LOCAL_CSV}"

st.caption(f"{I18N[lang]['last_sync']}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ----------------------------- TABS: VIEW / ADMIN / RECORD -------------------
if not st.session_state["is_admin"] and ADMIN_PASSWORD and st.session_state.get("pw_input") == ADMIN_PASSWORD:
    st.session_state["is_admin"] = True

admin_visible = st.session_state["is_admin"]

tab_labels = [I18N[lang]['latest']]
if admin_visible:
    tab_labels.append("Admin")
tab_labels.append("Record")

tabs = st.tabs(tab_labels)

# ---------- TAB 1: Latest (read-only) -------------------------------------
with tabs[0]:
    st.subheader(I18N[lang]["latest"])
    if df.empty:
        st.info(I18N[lang]["empty"])
    else:
        dfx = df[(df["published"] == True) & (df["language"].str.lower() == lang)].copy()
        if dfx.empty:
            st.info(I18N[lang]["empty"])
        else:
            latest = dfx.iloc[0]
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"<span class='badge'>{latest['language'].upper()}</span>", unsafe_allow_html=True)
                st.markdown(f"## {latest['title']}")
                if pd.notna(latest.get("date")):
                    st.markdown(f"<div class='meta'>{latest['date'].strftime('%Y-%m-%d')}</div>", unsafe_allow_html=True)
                content = latest.get("content_md", "")
                content = content.replace("’", "'").replace("“", '"').replace("”", '"')
                st.markdown(
                    f"""
                    <div style="background-color:#f3f4f6; padding:1rem; border-radius:10px; color:#111827;">
                        {content}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.markdown(
                    f"""
                    <div style="text-align:center; margin-top:1rem;">
                        <img src="https://raw.githubusercontent.com/Ozzors/Leparinordique/main/assets/Screenshot%202025-09-05%20135650.png"
                             style="max-width:25%; border-radius:12px;">
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with c2:
                st.metric(I18N[lang]["published"], "✅")

# ---------- TAB 2: Admin (password + editor) -------------------------------
if admin_visible:
    with tabs[1]:
        st.subheader("Admin — Create / Edit editions")
        if st.session_state["admin_ask_stay"]:
            st.success("Edition saved and uploaded to GitHub ✅")
            st.info("Do you want to stay in admin mode?")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Stay admin", key="stay_admin_btn"):
                    st.session_state["admin_ask_stay"] = False
                    st.rerun()
            with col_b:
                if st.button("Exit admin", key="exit_admin_btn"):
                    st.session_state["admin_ask_stay"] = False
                    st.session_state["is_admin"] = False
                    if "pw_input" in st.session_state:
                        st.session_state["pw_input"] = ""
                    st.rerun()
        with st.form("editor_form"):
            col1, col2 = st.columns([1, 3])
            with col1:
                # <- Fecha por defecto en el admin (hoy)
                d = st.date_input("Date", value=date.today())
                language_field = st.selectbox("Language", options=["en", "fr"], index=0)
                published_field = st.checkbox("Published", value=True)
            with col2:
                title_field = st.text_input("Title")
                content_field = st.text_area("Content (Markdown)", height=300)
            submitted = st.form_submit_button("Save edition")
        if submitted:
            edition_id = f"{d.strftime('%Y%m%d')}-{language_field}-{int(time.time())}"
            new_row = {
                "edition_id": edition_id,
                "date": d.strftime("%Y-%m-%d"),
                "language": language_field,
                "title": title_field,
                "content_md": content_field,
                "published": str(bool(published_field)).upper(),
            }
            if df is None or df.empty:
                new_df = pd.DataFrame([new_row])
            else:
                new_df = pd.concat([pd.DataFrame([new_row]), df], ignore_index=True)
            save_editions_local(new_df)
            if GITHUB_TOKEN and GITHUB_REPO:
                with st.spinner("Saving to GitHub..."):
                    res = save_editions_to_github(new_df, gh_sha)
                    if res:
                        load_editions_from_github.clear()
                        df, gh_sha = load_editions_from_github()
                        st.session_state["admin_ask_stay"] = True
                        st.rerun()
                    else:
                        st.error("Failed to save to GitHub — check logs and secrets.")
            else:
                st.success("Edition saved locally (editions.csv).")
                st.session_state["admin_ask_stay"] = True
                st.rerun()

# ---------- TAB 3: Record (history + downloads) ----------------------------
tab_record_index = -1 if admin_visible else 1
with tabs[tab_record_index]:
    st.subheader("📊 Record — All editions")
    if df.empty:
        st.info("No editions available.")
    else:
        q = st.text_input("Search titles/content...", value="")
        dfa = df.copy()
        if q:
            ql = q.lower().strip()
            dfa = dfa[
                dfa["title"].astype(str).str.lower().str.contains(ql)
                | dfa["content_md"].astype(str).str.lower().str.contains(ql)
            ]
        sports_emojis = ["⚽", "🏀", "🏈", "🎾", "🏐", "🏒", "🥊", "🏓"]
        for i, (_, row) in enumerate(dfa.iterrows()):
            emoji = sports_emojis[i % len(sports_emojis)]
            st.markdown(
                f"""
                <div class="edition-card">
                    <div class="badge">{row['language'].upper()} {emoji}</div>
                    <h4>{emoji} {row['title']}</h4>
                    <div class="meta">{row['date']}</div>
                    <p>{str(row['content_md'])[:180]}...</p>
                    <div class="meta">{'✅ Published' if row['published'] else '❌ Draft'}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        csv_bytes = dfa.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download CSV (filtered)",
            csv_bytes,
            file_name="editions_export.csv",
            mime="text/csv",
        )
        sel = st.selectbox(
            "Download single edition (ID)",
            options=list(dfa["edition_id"].astype(str)),
            index=0,
        )
        if sel:
            sel_row = dfa[dfa["edition_id"].astype(str) == sel].iloc[0]
            md_content = f"# {sel_row['title']}\n\n{sel_row['content_md']}"
            st.download_button(
                "⬇️ Download MD",
                md_content,
                file_name=f"{sel}.md",
                mime="text/markdown",
            )

# ----------------------------- FOOTER --------------------------------------
st.caption("© " + str(datetime.now().year) + " Le Pari Nordique — Built with Streamlit")
