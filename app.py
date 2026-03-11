import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF

# 1. CONFIGURACIÓN Y ESTILO INDUSTRIAL
st.set_page_config(page_title="Magallan | Sistema Central", layout="wide")

st.markdown("""
    <style>
    html, body, [class*="st-"] { font-size: 1.35rem !important; }
    label { font-size: 1.8rem !important; font-weight: bold !important; color: #1E3A8A !important; }
    [data-testid="stMetricValue"] { font-size: 5rem !important; font-weight: 800 !important; }
    
    .stButton>button {
        width: 100%; height: 110px; font-size: 2.5rem !important;
        background-color: #1E3A8A !important; color: white !important;
        border-radius: 25px !important; margin-top: 20px;
    }
    
    .atraso-card { 
        background-color: #FEF2F2; border-left: 20px solid #EF4444; 
        padding: 35px; border-radius: 20px; margin-bottom: 25px; 
        color: #991B1B; font-size: 2.2rem !important; font-weight: bold;
    }
    .info-card { 
        background-color: #F0F9FF; border-left: 20px solid #0EA5E9; 
        padding: 30px; border-radius: 20px; color: #075985; font-size: 1.8rem !important;
    }
    .last-update { font-size: 1rem; color: #666; font-style: italic; }
    </style>
    """, unsafe_allow_html=True)

# 2. CONEXIÓN Y CACHÉ ANTI-ERRORES
@st.cache_resource
def conectar_google():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scope))

@st.cache_data(ttl=300)
def cargar_datos_seguro():
    try:
        sh = conectar_google().open("Gestion_Magallan")
        def limpiar(n):
            try:
                df = pd.DataFrame(sh.worksheet(n).get_all_records())
                df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
                return df
            except: return pd.DataFrame()
        return limpiar("Proyectos"), limpiar("Logistica"), datetime.now().strftime("%H:%M:%S")
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame(), pd.DataFrame(), "Error"

df_p, df_l, ultima_act = cargar_datos_seguro()

# --- NAVEGACIÓN ---
st.sidebar.title("🏗️ MAGALLAN")
st.sidebar.markdown(f"<p class='last-update'>Sincronizado: {ultima_act}</p>", unsafe_allow_html=True)
user_name = st.sidebar.text_input("Operador:", value="Admin")
menu = st.sidebar.radio("IR A:", ["📈 TABLERO", "📝 GESTIÓN", "🚛 LOGÍSTICA"])

if not df_p.empty:
    # --- TABLERO ---
    if menu == "📈 TABLERO":
        st.title("📊 Tablero de Control")
        
        # BUSCADOR RÁPIDO EN TABLERO [Nuevo]
        st.subheader("🔍 Consultar Estado de Obra")
        df_p['busqueda'] = df_p['nro_ppto'].astype(str) + " - " + df_p['cliente'].astype(str)
        opciones_t = ["--- Buscar cortina... ---"] + list(df_p['busqueda'].unique())
        sel_t = st.selectbox("Ingrese nombre o presupuesto:", opciones_t, index=0, key="busq_tablero")
        
        if sel_t != "--- Buscar cortina... ---":
            nro_t = sel_t.split(" - ")[0]
            res = df_p[df_p['nro_ppto'].astype(str) == str(nro_t)].iloc[0]
            st.markdown(f"""
                <div class='info-card'>
                <b>Cliente:</b> {res['cliente']}<br>
                <b>Estado:</b> {res['estado_fabricacion'].upper()}<br>
                <b>Entrega:</b> {res['fecha_entrega']}
                </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # ALERTAS GENERALES
        hoy = datetime.now().date()
        df_p['fecha_dt'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
        atrasados = df_p[(df_p['fecha_dt'] < hoy) & (df_p['estado_fabricacion'] != "Entregado")]
        
        st.metric("VENCIDAS 🚨", len(atrasados))
        if not atrasados.empty:
            for _, r in atrasados.iterrows():
                st.markdown(f"<div class='atraso-card'>{r.get('cliente','')} - #{r.get('nro_ppto','')}</div>", unsafe_allow_html=True)
        
        if st.button("🔄 REFRESCAR TODO"):
            st.cache_data.clear()
            st.rerun()

    # --- GESTIÓN ---
    elif menu == "📝 GESTIÓN":
        st.title("📝 Gestión de Producción")
        t1, t2 = st.tabs(["🆕 Alta", "✏️ Editar"])
        
        with t1:
            with st.form("alta"):
                p_nro = st.number_input("Presupuesto #", step=1, value=0)
                p_cli = st.text_input("Cliente")
                p_fec = st.date_input("Fecha Prometida")
                if st.form_submit_button("REGISTRAR"):
                    sh = conectar_google().open("Gestion_Magallan")
                    sh.worksheet("Proyectos").append_row([p_nro, p_cli, "Esperando", str(datetime.now().date()), str(p_fec), 0, 0, "", "", ""])
                    sh.worksheet("Logistica").append_row([p_nro, "", str(p_fec), "Pendiente", ""])
                    st.cache_data.clear()
                    st.success("✅ GUARDADO")
                    st.rerun()

        with t2:
            df_p['busqueda'] = df_p['nro_ppto'].astype(str) + " - " + df_p['cliente'].astype(str)
            opciones_g = ["--- Seleccione Obra para Editar ---"] + list(df_p['busqueda'].unique())
            sel_g = st.selectbox("BUSCAR:", opciones_g, index=0)
            
            if sel_g != "--- Seleccione Obra para Editar ---":
                n_g = sel_g.split(" - ")[0]
                dat = df_p[df_p['nro_ppto'].astype(str) == str(n_g)].iloc[0]
                with st.form("edicion"):
                    est_op = ["Esperando", "Preparacion", "Terminado", "Entregado"]
                    idx_est = est_op.index(dat['estado_fabricacion']) if dat['estado_fabricacion'] in est_op else 0
                    nuevo_est = st.selectbox("ESTADO:", est_op, index=idx_est)
                    if st.form_submit_button("GUARDAR CAMBIOS"):
                        sh = conectar_google().open("Gestion_Magallan")
                        sh.worksheet("Proyectos").update_cell(df_p[df_p['nro_ppto'].astype(str) == str(n_g)].index[0] + 2, 3, nuevo_est)
                        st.cache_data.clear()
                        st.success("✅ ACTUALIZADO")
                        st.rerun()

    # --- LOGÍSTICA ---
    elif menu == "🚛 LOGÍSTICA":
        st.title("🚛 Logística e Instaladores")
        inst_list = ["--- Ver Todos ---"] + [i for i in df_l['tecnicos'].unique() if i]
        filtro = st.selectbox("FILTRAR POR INSTALADOR:", inst_list)
        
        df_m = pd.merge(df_p[['nro_ppto', 'cliente', 'estado_fabricacion']], df_l[['nro_ppto', 'tecnicos']], on='nro_ppto')
        if filtro != "--- Ver Todos ---":
            df_m = df_m[df_m['tecnicos'] == filtro]
        
        st.table(df_m)
        
        st.divider()
        opciones_l = ["--- Seleccione Obra para Asignar ---"] + list(df_p['busqueda'].unique())
        sel_l = st.selectbox("ASIGNAR EQUIPO A:", opciones_l, index=0)
        
        if sel_l != "--- Seleccione Obra para Asignar ---":
            n_l = sel_l.split(" - ")[0]
            with st.form("asig"):
                equipo = st.text_input("NOMBRE DEL EQUIPO:")
                if st.form_submit_button("CONFIRMAR ASIGNACIÓN"):
                    sh = conectar_google().open("Gestion_Magallan")
                    idx_l = df_l[df_l['nro_ppto'].astype(str) == str(n_l)].index[0] + 2
                    sh.worksheet("Logistica").update_cell(idx_l, 2, equipo)
                    st.cache_data.clear()
                    st.success("✅ EQUIPO ASIGNADO")
                    st.rerun()