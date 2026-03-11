import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# 1. ESTILO INDUSTRIAL CON SEMÁFORO VISUAL
st.set_page_config(page_title="Magallan | Gestión Visual", layout="wide")
st.markdown("""
    <style>
    html, body, [class*="st-"] { font-size: 1.35rem !important; }
    label { font-size: 1.8rem !important; font-weight: bold !important; color: #1E3A8A !important; }
    
    /* Botón Gigante */
    .stButton>button { width: 100%; height: 100px; font-size: 2.2rem !important; background-color: #1E3A8A !important; color: white !important; border-radius: 20px !important; }
    
    /* Colores del Semáforo */
    .status-esperando { background-color: #FEE2E2; border-left: 15px solid #EF4444; padding: 25px; border-radius: 15px; color: #991B1B; font-weight: bold; }
    .status-preparacion { background-color: #FEF3C7; border-left: 15px solid #F59E0B; padding: 25px; border-radius: 15px; color: #92400E; font-weight: bold; }
    .status-terminado { background-color: #D1FAE5; border-left: 15px solid #10B981; padding: 25px; border-radius: 15px; color: #065F46; font-weight: bold; }
    .status-entregado { background-color: #F3F4F6; border-left: 15px solid #6B7280; padding: 25px; border-radius: 15px; color: #374151; font-weight: bold; }
    
    .last-update { font-size: 1rem; color: #666; font-style: italic; }
    </style>
    """, unsafe_allow_html=True)

# 2. CONEXIÓN Y CACHÉ (SOLUCIÓN ERROR 429)
@st.cache_resource
def conectar_google():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope))

@st.cache_data(ttl=300)
def cargar_datos_seguro():
    try:
        sh = conectar_google().open("Gestion_Magallan")
        def limpiar(hoja):
            try:
                df = pd.DataFrame(sh.worksheet(hoja).get_all_records())
                df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
                return df
            except: return pd.DataFrame()
        return limpiar("Proyectos"), limpiar("Logistica"), datetime.now().strftime("%H:%M:%S")
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame(), pd.DataFrame(), "Error"

df_p, df_l, sincronizado_a_las = cargar_datos_seguro()

# --- BARRA LATERAL ---
st.sidebar.title("🏗️ GRUPO MAGALLAN")
st.sidebar.markdown(f"<p class='last-update'>Sincronizado: {sincronizado_a_las}</p>", unsafe_allow_html=True)

if st.sidebar.button("🔄 FORZAR ACTUALIZACIÓN"):
    st.cache_data.clear()
    st.rerun()

menu = st.sidebar.radio("IR A:", ["📈 TABLERO", "📝 GESTIÓN", "🚛 LOGÍSTICA"])

# --- VERIFICACIÓN DE DATOS ---
if df_p.empty or 'nro_ppto' not in df_p.columns:
    st.error("🚨 Error al leer datos del Excel.")
    st.stop()

df_p['busqueda'] = df_p['nro_ppto'].astype(str) + " - " + df_p['cliente'].astype(str)
opciones_vacias = ["--- Seleccione una Obra ---"] + list(df_p['busqueda'].unique())

# --- TABLERO (CON SEMÁFORO) ---
if menu == "📈 TABLERO":
    st.title("📊 Control de Producción")
    
    st.subheader("🔍 Consulta Rápida")
    sel_t = st.selectbox("Buscar por nombre o presupuesto:", opciones_vacias, index=0)
    
    if sel_t != "--- Seleccione una Obra ---":
        res = df_p[df_p['nro_ppto'].astype(str) == sel_t.split(" - ")[0]].iloc[0]
        est = str(res.get('estado_fabricacion', 'Esperando')).lower().strip()
        
        # Aplicación del Semáforo Visual
        clase = "status-esperando"
        if "preparacion" in est: clase = "status-preparacion"
        elif "terminado" in est: clase = "status-terminado"
        elif "entregado" in est: clase = "status-entregado"
        
        st.markdown(f"""
            <div class='{clase}'>
            PPTO: #{res['nro_ppto']} | CLIENTE: {res['cliente']}<br>
            ESTADO ACTUAL: {est.upper()}<br>
            FECHA ENTREGA: {res.get('fecha_entrega', 'S/D')}
            </div>
        """, unsafe_allow_html=True)

    st.divider()
    
    # Alertas Automáticas
    hoy = datetime.now().date()
    df_p['fecha_dt'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
    atrasados = df_p[(df_p['fecha_dt'] < hoy) & (df_p['estado_fabricacion'] != "Entregado")]
    
    st.metric("CORTINAS VENCIDAS 🚨", len(atrasados))
    for _, r in atrasados.iterrows():
        st.markdown(f"<div class='status-esperando'>⚠️ ATRASADO: {r['cliente']} (#{r['nro_ppto']})</div>", unsafe_allow_html=True)

# --- RESTO DEL CÓDIGO (GESTIÓN Y LOGÍSTICA) ---
elif menu == "📝 GESTIÓN":
    st.title("📝 Gestión y Edición")
    sel_g = st.selectbox("EDITAR ESTADO DE:", opciones_vacias, index=0)
    if sel_g != "--- Seleccione una Obra ---":
        n_g = sel_g.split(" - ")[0]
        dat = df_p[df_p['nro_ppto'].astype(str) == n_g].iloc[0]
        with st.form("edicion"):
            est_op = ["Esperando", "Preparacion", "Terminado", "Entregado"]
            idx_est = est_op.index(dat['estado_fabricacion']) if dat['estado_fabricacion'] in est_op else 0
            nuevo_est = st.selectbox("CAMBIAR ESTADO A:", est_op, index=idx_est)
            if st.form_submit_button("ACTUALIZAR"):
                sh = conectar_google().open("Gestion_Magallan")
                idx_excel = df_p[df_p['nro_ppto'].astype(str) == n_g].index[0] + 2
                sh.worksheet("Proyectos").update_cell(idx_excel, 3, nuevo_est)
                st.cache_data.clear()
                st.success("✅ ACTUALIZADO")
                st.rerun()

elif menu == "🚛 LOGÍSTICA":
    st.title("🚛 Logística e Instaladores")
    # Filtro por instalador
    inst_op = ["--- Ver Todos ---"] + [i for i in df_l['tecnicos'].unique() if i]
    filtro = st.selectbox("INSTALADOR:", inst_op)
    df_m = pd.merge(df_p[['nro_ppto', 'cliente', 'estado_fabricacion']], df_l[['nro_ppto', 'tecnicos']], on='nro_ppto', how='left')
    if filtro != "--- Ver Todos ---":
        df_m = df_m[df_m['tecnicos'] == filtro]
    st.dataframe(df_m, use_container_width=True)