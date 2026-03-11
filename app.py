import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF

# 1. CONFIGURACIÓN Y ESTILO DE ALTA VISIBILIDAD
st.set_page_config(page_title="Magallan | Gestión", layout="wide")

# Inyección de CSS para agrandar TODO
st.markdown("""
    <style>
    /* Agrandar textos generales y etiquetas */
    html, body, [class*="st-"] { font-size: 1.2rem !important; }
    label { font-size: 1.5rem !important; font-weight: bold !important; color: #1E3A8A !important; }
    
    /* Agrandar métricas del Dashboard */
    [data-testid="stMetricValue"] { font-size: 3.5rem !important; font-weight: 800 !important; }
    [data-testid="stMetricLabel"] { font-size: 1.3rem !important; }

    /* Tarjetas de alerta gigantes */
    .atraso-card { 
        background-color: #FEF2F2; border-left: 10px solid #EF4444; 
        padding: 25px; border-radius: 15px; margin-bottom: 20px; 
        color: #991B1B; font-size: 1.8rem !important; font-weight: bold;
    }
    .proximo-card { 
        background-color: #FFFBEB; border-left: 10px solid #F59E0B; 
        padding: 25px; border-radius: 15px; margin-bottom: 20px; 
        color: #92400E; font-size: 1.8rem !important; font-weight: bold;
    }

    /* Botones grandes y fáciles de tocar */
    .stButton>button {
        width: 100%; height: 80px; font-size: 1.8rem !important;
        background-color: #1E3A8A !important; color: white !important;
        border-radius: 15px !important; border: none !important;
    }
    
    /* Historial y Chat */
    .historial-item { font-size: 1.1rem; border-bottom: 2px solid #ddd; padding: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

# 2. CONEXIÓN Y CARGA (Mantiene el blindaje contra errores)
@st.cache_resource
def conectar_google():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Error de Conexión: {e}")
        st.stop()

def cargar_datos():
    try:
        sh = conectar_google().open("Gestion_Magallan")
        def get_df(nombre):
            try:
                df = pd.DataFrame(sh.worksheet(nombre).get_all_records())
                df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
                return df
            except: return pd.DataFrame()
        return sh, get_df("Proyectos"), get_df("Logistica"), get_df("Chat_Interno"), get_df("Historial")
    except Exception as e:
        st.error(f"Error al leer: {e}")
        return None, None, None, None, None

sh, df_p, df_l, df_c, df_h = cargar_datos()

# 3. INTERFAZ
st.sidebar.title("🏗️ MAGALLAN")
menu = st.sidebar.radio("MENÚ PRINCIPAL", ["📈 TABLERO", "📝 GESTIÓN", "🚛 LOGÍSTICA"], index=0)

if df_p is not None and not df_p.empty:
    if menu == "📈 TABLERO":
        st.title("📊 Control de Planta")
        hoy = datetime.now().date()
        df_p['fecha_dt'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
        
        atrasados = df_p[(df_p['fecha_dt'] < hoy) & (df_p['estado_fabricacion'] != "Entregado")]
        proximos = df_p[(df_p['fecha_dt'] >= hoy) & (df_p['fecha_dt'] <= hoy + timedelta(days=5)) & (df_p['estado_fabricacion'] != "Entregado")]

        c1, c2 = st.columns(2)
        c1.metric("VENCIDAS 🚨", len(atrasados))
        c2.metric("A ENTREGAR ⏳", len(proximos))

        if not atrasados.empty:
            st.markdown("### 🚨 PRIORIDAD MÁXIMA (VENCIDAS)")
            for _, r in atrasados.iterrows():
                st.markdown(f"<div class='atraso-card'>{r.get('cliente','S/D')} - #{r.get('nro_ppto','')}<br><small>Vencía: {r.get('fecha_entrega','')}</small></div>", unsafe_allow_html=True)

        if not proximos.empty:
            st.markdown("### ⏳ ENTREGAS ESTA SEMANA")
            for _, r in proximos.iterrows():
                st.markdown(f"<div class='proximo-card'>{r.get('cliente','S/D')} - #{r.get('nro_ppto','')}<br><small>Fecha: {r.get('fecha_entrega','')}</small></div>", unsafe_allow_html=True)

    elif menu == "📝 GESTIÓN":
        st.title("📝 Gestión de Cortinas")
        sel = st.selectbox("SELECCIONE UNA CORTINA:", df_p['nro_ppto'].unique())
        datos = df_p[df_p['nro_ppto'] == sel].iloc[0]

        with st.form("edicion_gigante"):
            st.markdown(f"## Editando Cortina: {datos.get('cliente')}")
            nuevo_est = st.selectbox("ESTADO ACTUAL:", ["Esperando", "Preparacion", "Terminado", "Entregado"], 
                                    index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(datos['estado_fabricacion']) if datos['estado_fabricacion'] in ["Esperando", "Preparacion", "Terminado", "Entregado"] else 0)
            nuevo_mat = st.text_area("MATERIALES PENDIENTES:", value=str(datos.get('materiales_pendientes', '')), height=150)
            
            if st.form_submit_button("GUARDAR CAMBIOS"):
                row_idx = df_p[df_p['nro_ppto'] == sel].index[0] + 2
                ws = sh.worksheet("Proyectos")
                ws.update_cell(row_idx, 3, nuevo_est)
                ws.update_cell(row_idx, 10, nuevo_mat)
                sh.worksheet("Historial").append_row([str(sel), datetime.now().strftime("%H:%M"), "Admin", f"Actualizó: {nuevo_est}"])
                st.success("✅ ¡CAMBIOS GUARDADOS!")
                st.rerun()