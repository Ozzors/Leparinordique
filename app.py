import streamlit as st
import pandas as pd
import os
import base64
import requests

# --- Configuración de la página ---
st.set_page_config(page_title="Le Pari Nordique", page_icon="🎯", layout="wide")

# --- Función: cargar datos desde CSV ---
def load_editions():
    if os.path.exists("editions.csv"):
        return pd.read_csv("editions.csv")
    else:
        return pd.DataFrame(columns=["Fecha", "Evento", "Ganador"])

# --- Función: guardar datos en CSV y GitHub ---
def save_editions(df):
    df.to_csv("editions.csv", index=False)

    repo = st.secrets["GITHUB_REPO"]
    branch = st.secrets.get("GITHUB_BRANCH", "main")
    github_token = st.secrets["GITHUB_TOKEN"]
    github_api = f"https://api.github.com/repos/{repo}/contents/editions.csv"

    with open("editions.csv", "rb") as f:
        content = base64.b64encode(f.read()).decode()

    headers = {"Authorization": f"token {github_token}"}

    # Verificar si el archivo ya existe en GitHub
    resp = requests.get(github_api, headers=headers, params={"ref": branch})
    if resp.status_code == 200:
        sha = resp.json()["sha"]
    else:
        sha = None

    data = {
        "message": "Actualizar editions.csv desde la app",
        "content": content,
        "branch": branch,
    }
    if sha:
        data["sha"] = sha

    put_resp = requests.put(github_api, headers=headers, json=data)

    if put_resp.status_code not in [200, 201]:
        st.error(f"Error al guardar en GitHub: {put_resp.text}")

# --- Función: subir logo y guardar en GitHub ---
def upload_logo():
    st.subheader("Subir logo")
    uploaded_file = st.file_uploader("Elige un archivo de imagen", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        # Mostrar vista previa
        st.image(uploaded_file, caption="Vista previa", width=200)

        if st.button("Guardar logo"):
            # Guardar localmente en carpeta assets
            os.makedirs("assets", exist_ok=True)
            local_path = "assets/logo.png"
            with open(local_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success("Logo guardado localmente en assets/logo.png ✅")

            # Subir a GitHub
            repo = st.secrets["GITHUB_REPO"]
            branch = st.secrets.get("GITHUB_BRANCH", "main")
            github_token = st.secrets["GITHUB_TOKEN"]
            github_api = f"https://api.github.com/repos/{repo}/contents/assets/logo.png"

            with open(local_path, "rb") as f:
                content = base64.b64encode(f.read()).decode()

            headers = {"Authorization": f"token {github_token}"}

            # Verificar si el archivo ya existe en GitHub
            resp = requests.get(github_api, headers=headers, params={"ref": branch})
            if resp.status_code == 200:
                sha = resp.json()["sha"]
            else:
                sha = None

            data = {
                "message": "Actualizar logo.png desde la app",
                "content": content,
                "branch": branch,
            }
            if sha:
                data["sha"] = sha

            put_resp = requests.put(github_api, headers=headers, json=data)

            if put_resp.status_code in [200, 201]:
                st.success("Logo subido/actualizado en GitHub ✅")
            else:
                st.error(f"Error al subir logo a GitHub: {put_resp.text}")

# --- Cargar logo (si existe) ---
def show_logo():
    if os.path.exists("assets/logo.png"):
        st.image("assets/logo.png", width=200)
    else:
        st.write("🎯 Le Pari Nordique")

# --- Interfaz ---
show_logo()

# --- Sidebar ---
with st.sidebar:
    if os.path.exists("assets/logo.png"):
        st.image("assets/logo.png", width=150)
    st.title("Le Pari Nordique")
    menu = st.radio("Navegación", ["Inicio", "Historial", "Admin"])

# --- Contenido principal ---
if menu == "Inicio":
    st.header("📊 Bienvenido a Le Pari Nordique")
    st.write("Explora los resultados y el historial de apuestas deportivas.")

elif menu == "Historial":
    st.header("📜 Historial de ediciones")
    df = load_editions()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay ediciones registradas aún.")

elif menu == "Admin":
    st.header("🔧 Panel de administración")
    password = st.text_input("Contraseña", type="password")
    if password == st.secrets["ADMIN_PASSWORD"]:
        st.success("Acceso concedido ✅")

        # --- Gestión de ediciones ---
        st.subheader("Agregar nueva edición")
        fecha = st.date_input("Fecha")
        evento = st.text_input("Evento")
        ganador = st.text_input("Ganador")
        if st.button("Guardar edición"):
            df = load_editions()
            df = pd.concat(
                [df, pd.DataFrame({"Fecha": [fecha], "Evento": [evento], "Ganador": [ganador]})],
                ignore_index=True,
            )
            save_editions(df)
            st.success("Edición guardada ✅")

        st.subheader("Ediciones actuales")
        df = load_editions()
        st.dataframe(df, use_container_width=True)

        # --- Configuración del logo ---
        with st.expander("Configuración del logo"):
            upload_logo()

    else:
        st.warning("Introduce la contraseña para acceder.")


