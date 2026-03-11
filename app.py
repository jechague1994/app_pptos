import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF
import time

# 1. ESTILO DE ALTA VISIBILIDAD (TAMAÑO TALLER)
st.set_page_config(page_title="Magallan | Gestión Total", layout="wide")

st.markdown("""
    <style>
    html, body, [class*="st-"] { font-size: 1.35rem !important; }
    label { font-size: 1.8rem !important; font-weight: bold !important; color: #1E3A8A !important; }
    [data-testid="stMetricValue"] { font-size: 5rem !important; font-weight: 800 !important; }
    
    /* Alertas Masivas */
    .atraso-card { 
        background-color: #FEF2F2; border-left: 20px solid #EF4444; 
        padding: 35px; border-radius: 20px; margin-bottom: 25px; 
        color: #991B1B; font-size: 2.2rem !important; font-weight: bold;
    }
    .proximo-card { 
        background-color: #FFFBEB; border-left: 20px solid #F59E0B; 
        padding: 35px; border-radius: 20px; margin-bottom: 25px; 
        color: #92400E; font-size: 2.2rem !important; font-weight: bold;
    }

    /* Botones Gigantes */
    .stButton>button {
        width: 100%; height: 110px; font-size: 2.5rem !important;
        background-color: #1E3A8A !important; color: white !important;
        border-radius: 25px !important; margin-top: 20px;
    }
    
    .last-update { font-size: 1rem; color: #666; font-style: italic; }
    </style>
    """, unsafe_allow_html=True)

# 2. CONEXIÓN Y CACHÉ (SOLUCIÓN ERROR 429)
@st.cache_resource
def conectar_google():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(credentials)

@st.cache_data(ttl=300) # Evita saturar la API (actualiza cada 5 min)
def cargar_datos_seguro():
    try:
        sh = conectar_google().open("Gestion_Magallan")
        def limpiar(nombre):
            try:
                df = pd.DataFrame(sh.worksheet(nombre).get_all_records())
                df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
                return df
            except: return pd.DataFrame()
        return limpiar("Proyectos"), limpiar("Logistica"), limpiar("Historial"), datetime.now().strftime("%H:%M:%S")
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "Error"

df_p, df_l, df_h, ultima_act = cargar_datos_seguro()

# 3. PDF Y FUNCIONES
def generar_pdf(cortina):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(30, 58, 138); pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", "B", 25)
    pdf.cell(0, 20, "GRUPO MAGALLAN", ln=True, align="C")
    pdf.set_text_color(0, 0, 0); pdf.ln(25)
    pdf.set_font("Arial", "B", 16); pdf.cell(0, 10, f"CLIENTE: {cortina.get('cliente')}", ln=True)
    pdf.set_font("Arial", "", 14); pdf.cell(0, 10, f"Presupuesto: #{cortina.get('nro_ppto')}", ln=True)
    pdf.ln(10); pdf.cell(190, 12, "MATERIALES PENDIENTES:", ln=True, fill=True)
    pdf.multi_cell(0, 10, str(cortina.get('materiales_pendientes', 'Sin registrar')))
    return pdf.output(dest="S").encode("latin-1")

# --- NAVEGACIÓN ---
st.sidebar.title("🏗️ MAGALLAN")
st.sidebar.markdown(f"*Última actualización: {ultima_act}*")
user_name = st.sidebar.text_input("Operador:", value="Admin")
menu = st.sidebar.radio("IR A:", ["📈 TABLERO", "📝 GESTIÓN", "🚛 LOGÍSTICA"])

if not df_p.empty:
    # --- TABLERO ---
    if menu == "📈 TABLERO":
        st.title("📊 Control de Producción")
        hoy = datetime.now().date()
        df_p['fecha_dt'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
        
        atrasados = df_p[(df_p['fecha_dt'] < hoy) & (df_p['estado_fabricacion'] != "Entregado")]
        proximos = df_p[(df_p['fecha_dt'] >= hoy) & (df_p['fecha_dt'] <= hoy + timedelta(days=5)) & (df_p['estado_fabricacion'] != "Entregado")]

        c1, c2 = st.columns(2)
        c1.metric("VENCIDAS 🚨", len(atrasados))
        c2.metric("PROX. 5 DÍAS ⏳", len(proximos))

        if not atrasados.empty:
            st.markdown("### 🚨 URGENTE")
            for _, r in atrasados.iterrows():
                st.markdown(f"<div class='atraso-card'>{r.get('cliente','')} - #{r.get('nro_ppto','')}<br><small>FECHA LÍMITE: {r.get('fecha_entrega','')}</small></div>", unsafe_allow_html=True)

        if st.button("🔄 ACTUALIZAR DATOS AHORA"):
            st.cache_data.clear()
            st.rerun()

    # --- GESTIÓN ---
    elif menu == "📝 GESTIÓN":
        st.title("📝 Gestión y Búsqueda")
        t1, t2 = st.tabs(["🆕 Alta de Obra", "✏️ Editar / Buscar"])
        
        with t1:
            with st.form("alta"):
                st.markdown("### Nueva Cortina")
                c1, c2 = st.columns(2)
                p_nro = c1.number_input("Nro Presupuesto", step=1)
                p_cli = c1.text_input("Nombre del Cliente")
                p_fec = c2.date_input("Fecha Entrega")
                p_mat = st.text_area("Materiales Necesarios")
                if st.form_submit_button("GUARDAR EN SISTEMA"):
                    sh = conectar_google().open("Gestion_Magallan")
                    sh.worksheet("Proyectos").append_row([p_nro, p_cli, "Esperando", str(datetime.now().date()), str(p_fec), 0, 0, "", "", p_mat])
                    sh.worksheet("Logistica").append_row([p_nro, "", str(p_fec), "Pendiente", ""])
                    st.cache_data.clear()
                    st.success("✅ CORTINA REGISTRADA")
                    st.rerun()

        with t2:
            # Buscador por Nombre o Ppto
            df_p['busqueda'] = df_p['nro_ppto'].astype(str) + " - " + df_p['cliente'].astype(str)
            sel_b = st.selectbox("BUSCAR POR CLIENTE:", df_p['busqueda'].unique())
            sel_nro = sel_b.split(" - ")[0]
            datos = df_p[df_p['nro_ppto'].astype(str) == str(sel_nro)].iloc[0]
            
            with st.form("edit_gigante"):
                st.markdown(f"## Cliente: {datos['cliente']}")
                est_op = ["Esperando", "Preparacion", "Terminado", "Entregado"]
                nuevo_est = st.selectbox("ESTADO ACTUAL:", est_op, index=est_op.index(datos['estado_fabricacion']) if datos['estado_fabricacion'] in est_op else 0)
                nuevo_mat = st.text_area("MATERIALES PENDIENTES:", value=str(datos.get('materiales_pendientes', '')))
                if st.form_submit_button("ACTUALIZAR ESTADO"):
                    sh = conectar_google().open("Gestion_Magallan")
                    ws = sh.worksheet("Proyectos")
                    idx = df_p[df_p['nro_ppto'].astype(str) == str(sel_nro)].index[0] + 2
                    ws.update_cell(idx, 3, nuevo_est)
                    ws.update_cell(idx, 10, nuevo_mat)
                    sh.worksheet("Historial").append_row([str(sel_nro), datetime.now().strftime("%d/%m %H:%M"), user_name, f"Cambio a {nuevo_est}"])
                    st.cache_data.clear()
                    st.success("✅ CAMBIOS GUARDADOS")
                    st.rerun()
            st.download_button("📥 DESCARGAR PDF PARA TALLER", data=generar_pdf(datos), file_name=f"Obra_{sel_nro}.pdf")

    # --- LOGÍSTICA ---
    elif menu == "🚛 LOGÍSTICA":
        st.title("🚛 Instalaciones")
        df_p['busqueda'] = df_p['nro_ppto'].astype(str) + " - " + df_p['cliente'].astype(str)
        sel_l = st.selectbox("SELECCIONE OBRA:", df_p['busqueda'].unique())
        nro_l = sel_l.split(" - ")[0]
        
        idx_l = df_l[df_l['nro_ppto'].astype(str) == str(nro_l)].index
        if not idx_l.empty:
            with st.form("log"):
                inst = st.text_input("INSTALADORES ASIGNADOS:", value=df_l.loc[idx_l[0], 'tecnicos'])
                if st.form_submit_button("ASIGNAR EQUIPO"):
                    sh = conectar_google().open("Gestion_Magallan")
                    sh.worksheet("Logistica").update_cell(int(idx_l[0])+2, 2, inst)
                    st.cache_data.clear()
                    st.success("✅ INSTALADORES ASIGNADOS")
                    st.rerun()