import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. Configuración de página y Estilos de Alerta
st.set_page_config(page_title="Grupo Magallan | Gestión 360", layout="wide")

st.markdown("""
    <style>
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b; }
    .alerta-roja { color: white; background-color: #ff4b4b; padding: 10px; border-radius: 5px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 2. Conexión Robusta con Google Sheets
@st.cache_resource
def conectar_google():
    try:
        # Usamos scopes amplios para evitar el error 403 de tus capturas
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"❌ Error de autenticación: {e}")
        st.stop()

client = conectar_google()
SHEET_NAME = "Gestion_Magallan"

# 3. Carga de datos con limpieza de columnas
def cargar_datos():
    try:
        sh = client.open(SHEET_NAME)
        
        # Cargamos las 3 pestañas confirmadas en tus fotos
        ws_p = sh.worksheet("Proyectos")
        ws_l = sh.worksheet("Logistica")
        ws_c = sh.worksheet("Chat_Interno")
        
        df_p = pd.DataFrame(ws_p.get_all_records())
        df_l = pd.DataFrame(ws_l.get_all_records())
        df_c = pd.DataFrame(ws_c.get_all_records())

        # LIMPIEZA CRÍTICA: Quitamos espacios y normalizamos nombres de columnas
        for df in [df_p, df_l, df_c]:
            df.columns = df.columns.str.strip() 
            
        return sh, df_p, df_l, df_c
    except Exception as e:
        st.error(f"⚠️ Error al leer las pestañas: {e}")
        st.info("Asegúrate de que los nombres de las pestañas sean exactos: 'Proyectos', 'Logistica' y 'Chat_Interno'")
        return None, None, None, None

sh, df_p, df_l, df_c = cargar_datos()

# --- NAVEGACIÓN ---
st.sidebar.title("🏗️ Grupo Magallan")
menu = st.sidebar.radio("Navegación", ["📈 Tablero de Control", "🏗️ Gestión de Obras", "🚚 Logística y Chat"])

# --- SECCIÓN 1: TABLERO CON ALERTAS VISUALES ---
if menu == "📈 Tablero de Control":
    st.header("📈 Tablero de Control Inteligente")
    
    if df_p is not None and not df_p.empty:
        # Verificamos si la columna existe después de la limpieza
        col_fecha = "Fecha_Entrega"
        if col_fecha in df_p.columns:
            hoy = datetime.now().date()
            
            # Convertimos a fecha de forma segura
            df_p[col_fecha] = pd.to_datetime(df_p[col_fecha], errors='coerce').dt.date
            
            # Filtro de obras atrasadas (No entregadas y fecha pasada)
            obras_atrasadas = df_p[(df_p[col_fecha] < hoy) & (df_p['Estado_Fabricacion'] != "Entregado")].copy()
            
            # Métricas
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Obras Totales", len(df_p))
            with c2:
                color_atraso = "normal" if len(obras_atrasadas) == 0 else "inverse"
                st.metric("Entregas Atrasadas ⚠️", len(obras_atrasadas), delta=len(obras_atrasadas), delta_color=color_atraso)
            with c3:
                # Cálculo de deuda (Total - Pagado)
                deuda = pd.to_numeric(df_p['Monto_Total_Ars'], errors='coerce').sum() - pd.to_numeric(df_p['Pagado_Ars'], errors='coerce').sum()
                st.metric("Saldo Pendiente Total", f"$ {deuda:,.2f}")

            st.divider()

            if not obras_atrasadas.empty:
                st.markdown('<p class="alerta-roja">🚨 ATENCIÓN: LAS SIGUIENTES OBRAS HAN SUPERADO SU FECHA DE ENTREGA</p>', unsafe_allow_html=True)
                # Mostramos solo lo importante
                st.table(obras_atrasadas[['Nro_Ppto', 'Cliente', 'Fecha_Entrega', 'Estado_Fabricacion']])
            else:
                st.success("✅ No hay obras con entrega retrasada hoy.")
        else:
            st.warning(f"No se detectó la columna '{col_fecha}'. Verifica que no tenga espacios ocultos en el Excel.")

# (El resto de las secciones se mantienen para cargar y editar datos)
else:
    st.info("Utiliza el menú lateral para gestionar obras o ver el chat.")