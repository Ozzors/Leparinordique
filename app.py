import os
import base64
import io
import time
from datetime import datetime, date
from typing import Optional, Tuple

import pandas as pd
import requests
import streamlit as st

# ----------------------------- PAGE CONFIG & THEME ---------------------------
st.set_page_config(
    page_title="Le Pari Nordique – Newsletter",
    page_icon="🏅",
    layout="wide"
)

PRIMARY = "#0EA5E9"
ACCENT = "#F59E0B"
CUSTOM_CSS = f"""
<style>
:root {{
  --primary: {PRIMARY};
  --accent: {ACCENT};
}}
.block-container {{
  padding-top: 2rem;
}}
.kicker {{
  color: var(--primary);
  font-weight: 600;
  text-transform: uppercase;
  font-size: .85rem;
}}
.edition-card {{
  border: 1px solid rgba(0,0,0,.06);
  border-radius: 16px;
  padding: 1rem 1.25rem;
  box-shadow: 0 2px 12px rgba(0,0,0,.04);
}}
.badge {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: .75rem;
  background: rgba(14,165,233,.1);
  color: var(--primary);
  margin-right: .5rem;
}}
.meta {{
  color: #6b7280;
  font-size: .9rem;
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ----------------------------- I18N ------------------------------------------
I18N = {
    "en": {
        "app_title": "Le Pari Nordique",
        "subtitle": "Sports betting insights — admin editor",
        "latest": "Latest Edition",
        "archive": "Archive",
        "stats": "Performance",
        "refresh": "Refresh",
        "last_sync": "Last sync",
        "empty": "No editions published yet in this language.",
        "search": "Search in titles...",
        "published": "Published",
        "admin": "Admin — Create / Edit editions",
        "record": "Record — All editions",
        "password": "Admin password",
        "save": "Save edition",
        "upload_logo": "Upload a logo (PNG)",
        "save_logo": "Save logo",
    },
    "fr": {
        "app_title": "Le Pari Nordique",
        "subtitle": "Paris sportifs — éditeur admin",
        "latest": "Dernière édition",
        "archive": "Archives",
        "stats": "Performance",
        "refresh": "Rafraîchir",
        "last_sync": "Dernière synchro",
        "empty": "Aucune édition publiée pour cette langue.",
        "search": "Rechercher dans les titres...",
        "published": "Publié",
        "admin": "Admin — Créer / Modifier des éditions",
        "record": "Historique — Toutes les éditions",
        "password": "Mot de passe admin",
        "save": "Enregistrer l’édition",
        "upload_logo": "Téléverser un logo (PNG)",
        "save_logo": "Enregistrer le logo",
    },
}

# ----------------------------- CONFIG: GitHub / Local ------------------------
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "").strip()
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "").strip()
GITHUB_PATH = st.secrets.get("GITHUB_PATH", "editions.csv").strip()
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main").strip()
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "").strip()

LOCAL_CSV = "editions.csv"

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

# ----------------------------- DATA LOADING ----------------------------------
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
    df = df.sort_values("date", ascending=False, na_position="last").reset_index(drop=True)
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

# ----------------------------- LOGO UPLOAD -----------------------------------

def upload_logo():
    st.subheader("Upload app logo")
    uploaded_file = st.file_uploader(
        "Choose a logo (PNG or JPG/JPEG, max 2MB)", 
        type=["png", "jpg", "jpeg"]
    )
    if uploaded_file is not None:
        # Validar tamaño (opcional)
        if uploaded_file.size > 2 * 1024 * 1024:
            st.error("File too large. Max 2MB.")
            return
        
        # Guardar localmente
        os.makedirs("assets", exist_ok=True)
        ext = uploaded_file.name.split(".")[-1].lower()
        local_path = f"assets/logo.png"  # siempre PNG local
        with open(local_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Logo saved locally as {local_path}")
        st.image(local_path, width=200)

        # Subir a GitHub
        if GITHUB_TOKEN and GITHUB_REPO:
            # Convertir a PNG bytes aunque venga JPG
            img_bytes = uploaded_file.getbuffer()
            github_path = "assets/logo.png"  # ruta en GitHub
            try:
                # Verificar si ya existe para obtener SHA
                existing_content, sha = github_get_file(GITHUB_REPO, github_path, GITHUB_TOKEN, branch=GITHUB_BRANCH)
                res = github_put_file(
                    repo=GITHUB_REPO,
                    path=github_path,
                    token=GITHUB_TOKEN,
                    content_bytes=img_bytes,
                    message=f"Update logo — {datetime.utcnow().isoformat()}",
                    sha=sha,
                    branch=GITHUB_BRANCH
                )
                if res:
                    st.success("Logo uploaded to GitHub ✅")
                else:
                    st.error("Error uploading logo to GitHub. Check repo, branch, and token.")
            except Exception as e:
                st.error(f"Exception uploading logo to GitHub: {e}")


# ----------------------------- SIDEBAR ---------------------------------------
with st.sidebar:
    st.markdown("<div class='kicker'>Newsletter</div>", unsafe_allow_html=True)
    st.title("Le Pari Nordique 🏅")
    st.caption("Admin editor — saves to GitHub or local CSV")
    lang = st.radio("Language / Langue", options=["fr", "en"], index=1, format_func=lambda x: "Français" if x == "fr" else "English")
    if st.button(I18N[lang]["refresh"], use_container_width=True):
        load_editions_from_github.clear()

# ----------------------------- LOAD DATA -------------------------------------
if GITHUB_TOKEN and GITHUB_REPO:
    df, gh_sha = load_editions_from_github()
    source = f"GitHub: {GITHUB_REPO}/{GITHUB_PATH} (branch: {GITHUB_BRANCH})"
else:
    df = load_editions_local()
    gh_sha = None
    source = f"Local file: {LOCAL_CSV}"

st.caption(f"Source: {source}")
st.caption(f"{I18N[lang]['last_sync']}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ----------------------------- TABS ------------------------------------------
tabs = st.tabs([I18N[lang]['latest'], I18N[lang]['admin'], I18N[lang]['record']])

# ---------- TAB 1: Latest ----------------------------------------------------
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
                st.markdown(latest.get("content_md", ""))
            with c2:
                st.metric("ID", str(latest.get("edition_id", "-")))
                st.metric(I18N[lang]["published"], "✅")

# ---------- TAB 2: Admin -----------------------------------------------------
with tabs[1]:
    st.subheader(I18N[lang]["admin"])
    if not ADMIN_PASSWORD:
        st.warning("No ADMIN_PASSWORD configured in secrets.")
    pw = st.text_input(I18N[lang]["password"], type="password")
    if ADMIN_PASSWORD and pw != ADMIN_PASSWORD:
        st.info("Enter admin password to unlock editor.")
    else:
        with st.form("editor_form"):
            col1, col2 = st.columns([1, 3])
            with col1:
                d = st.date_input("Date", value=date.today())
                language_field = st.selectbox("Language", options=["en", "fr"], index=0)
                published_field = st.checkbox(I18N[lang]["published"], value=True)
            with col2:
                title_field = st.text_input("Title")
                content_field = st.text_area("Content (Markdown)", height=300)
            submitted = st.form_submit_button(I18N[lang]["save"])
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
                        st.success("Edition saved and uploaded to GitHub ✅")
                        load_editions_from_github.clear()
                        df, gh_sha = load_editions_from_github()
                    else:
                        st.error("Failed to save to GitHub.")
                else:
                    st.success("Edition saved locally (editions.csv).")
        upload_logo()

# ---------- TAB 3: Record ----------------------------------------------------
with tabs[2]:
    st.subheader(I18N[lang]["record"])
    if df.empty:
        st.info("No editions available.")
    else:
        q = st.text_input(I18N[lang]["search"], value="")
        dfa = df.copy()
        if q:
            ql = q.lower().strip()
            dfa = dfa[dfa["title"].astype(str).str.lower().str.contains(ql) | dfa["content_md"].astype(str).str.lower().str.contains(ql)]
        st.dataframe(dfa.reset_index(drop=True))
        csv_bytes = dfa.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV (filtered)", csv_bytes, file_name="editions_export.csv", mime="text/csv")
        sel = st.selectbox("Download single edition (ID)", options=list(dfa["edition_id"].astype(str)), index=0)
        if sel:
            sel_row = dfa[dfa["edition_id"].astype(str) == sel].iloc[0]
            md_content = f"# {sel_row['title']}\n\n{sel_row['content_md']}"
            st.download_button("Download MD", md_content, file_name=f"{sel}.md", mime="text/markdown")

# ----------------------------- FOOTER ----------------------------------------
st.caption("© " + str(datetime.now().year) + " Le Pari Nordique — Built with Streamlit")


