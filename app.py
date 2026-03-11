import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Configuración Inicial
st.set_page_config(page_title="Grupo Magallan | Gestión", layout="wide")

@st.cache_resource
def conectar_google():
    try:
        # Scopes amplios para lectura y escritura
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"❌ Error de Secretos/Conexión: {e}")
        st.stop()

client = conectar_google()
SHEET_NAME = "Gestion_Magallan"

def cargar_datos():
    try:
        sh = client.open(SHEET_NAME)
        # Pestañas confirmadas en tus capturas
        df_p = pd.DataFrame(sh.worksheet("Proyectos").get_all_records())
        df_l = pd.DataFrame(sh.worksheet("Logistica").get_all_records())
        df_c = pd.DataFrame(sh.worksheet("Chat_Interno").get_all_records())
        
        # LIMPIEZA: Quitamos espacios invisibles en los encabezados
        for df in [df_p, df_l, df_c]:
            df.columns = df.columns.str.strip()
            
        return sh, df_p, df_l, df_c
    except Exception as e:
        st.error(f"⚠️ Error al abrir pestañas: {e}")
        return None, None, None, None

sh, df_p, df_l, df_c = cargar_datos()

# --- TABLERO DE CONTROL ---
if df_p is not None:
    st.title("📈 Tablero de Control Inteligente")
    
    # Validamos que 'Fecha_Entrega' exista realmente
    if 'Fecha_Entrega' in df_p.columns:
        hoy = datetime.now().date()
        # Conversión segura a fecha (ignora horas si las hay)
        df_p['Fecha_Entrega_DT'] = pd.to_datetime(df_p['Fecha_Entrega'], errors='coerce').dt.date
        
        # Filtro de Atrasados
        atrasados = df_p[(df_p['Fecha_Entrega_DT'] < hoy) & (df_p['Estado_Fabricacion'] != "Entregado")]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Obras Totales", len(df_p))
        c2.metric("Entregas Vencidas ⚠️", len(atrasados), delta=len(atrasados), delta_color="inverse")
        
        # Cálculo de Saldo (Monto - Pagado)
        deuda = pd.to_numeric(df_p['Monto_Total_Ars'], errors='coerce').sum() - pd.to_numeric(df_p['Pagado_Ars'], errors='coerce').sum()
        c3.metric("Saldo Pendiente", f"$ {deuda:,.2f}")
        
        if not atrasados.empty:
            st.warning("🚨 Obras que requieren atención inmediata:")
            st.dataframe(atrasados[['Nro_Ppto', 'Cliente', 'Fecha_Entrega']])
    else:
        st.info("💡 Sugerencia: Revisa que el encabezado 'Fecha_Entrega' no tenga errores de escritura en el Excel.")