import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Configuración inicial
st.set_page_config(page_title="Grupo Magallan", layout="wide")
st.title("🏗️ Panel de Gestión Operativa - Grupo Magallan")

# 1. Configurar Credenciales desde st.secrets
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = st.secrets["gcp_service_account"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(credentials)

# 2. Abrir el archivo por su nombre exacto
SHEET_NAME = "Gestion_Magallan"

@st.cache_data(ttl=60)
def cargar_todo():
    sh = client.open(SHEET_NAME)
    
    # Cargar cada pestaña
    p = pd.DataFrame(sh.worksheet("Proyectos").get_all_records())
    l = pd.DataFrame(sh.worksheet("Logistica").get_all_records())
    c = pd.DataFrame(sh.worksheet("Chat_Interno").get_all_records())
    
    # Limpiar columnas
    for df in [p, l, c]:
        df.columns = [col.strip().lower() for col in df.columns]
    return p, l, c

try:
    df_p, df_l, df_c = cargar_todo()
    
    # Sidebar
    st.sidebar.success("✅ Conectado")
    ppto_sel = st.sidebar.selectbox("Seleccione Presupuesto:", df_p["nro_ppto"].unique())
    
    # Datos filtrados
    resumen = df_p[df_p["nro_ppto"] == ppto_sel].iloc[0]

    # Tabs
    t1, t2, t3 = st.tabs(["📊 Fabricación", "🚚 Logística", "💬 Chat"])

    with t1:
        st.subheader(f"Cliente: {resumen['cliente']}")
        c1, c2 = st.columns(2)
        c1.metric("Estado", resumen['estado_fabricacion'])
        total = float(resumen['monto_total_ars'])
        pagado = float(resumen['pagado_ars'])
        c2.metric("Saldo Pendiente", f"$ {total - pagado:,.2f}")

    with t2:
        if ppto_sel in df_l["nro_ppto"].values:
            log = df_l[df_l["nro_ppto"] == ppto_sel].iloc[0]
            st.write(f"*Técnicos:* {log['tecnicos']}")
            st.info(f"*Fecha:* {log['fecha_instalacion']}")
        else:
            st.warning("Sin datos de logística.")

    with t3:
        chat = df_c[df_c["nro_ppto"].astype(str) == str(ppto_sel)]
        for _, m in chat.iterrows():
            with st.chat_message("user"):
                st.write(f"*{m['usuario']}*: {m['mensaje']}")

except Exception as e:
    st.error(f"Error crítico: {e}")
    st.info("Asegúrate de que el archivo de Google Sheets se llame exactamente 'Gestion_Magallan'.")