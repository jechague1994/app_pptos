import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Grupo Magallan", layout="wide")
st.title("🏗️ Panel de Gestión Operativa - Grupo Magallan")

# Intentar cargar secretos con manejo de errores
try:
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(credentials)
    else:
        st.error("❌ No se encontró la clave 'gcp_service_account' en los Secrets.")
        st.stop()
except Exception as e:
    st.error(f"❌ Error configurando credenciales: {e}")
    st.stop()

# Nombre exacto de tu archivo en Google Drive
SHEET_NAME = "Gestion_Magallan"

@st.cache_data(ttl=60)
def cargar_datos():
    try:
        sh = client.open(SHEET_NAME)
        # Cargamos las 3 pestañas confirmadas en tus capturas
        p = pd.DataFrame(sh.worksheet("Proyectos").get_all_records())
        l = pd.DataFrame(sh.worksheet("Logistica").get_all_records())
        c = pd.DataFrame(sh.worksheet("Chat_Interno").get_all_records())
        return p, l, c
    except Exception as e:
        st.error(f"❌ Error al abrir las pestañas: {e}")
        return None, None, None

df_p, df_l, df_c = cargar_datos()

if df_p is not None:
    # El resto de tu lógica de pestañas y visualización...
    st.sidebar.success("✅ Conectado a Gestión_Magallan")
    # ... (código de filtrado por nro_ppto)