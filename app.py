import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fpdf import FPDF
import base64

# 1. CONFIGURACIÓN DE INTERFAZ
st.set_page_config(page_title="Grupo Magallan | Sistema Operativo", layout="wide", page_icon="🏗️")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-top: 4px solid #10b981; }
    .atraso-card { background-color: #fff5f5; border-left: 5px solid #ef4444; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 2. CONEXIÓN Y CARGA DE DATOS
@st.cache_resource
def conectar_google():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"❌ Error de Conexión: {e}")
        st.stop()

def cargar_datos():
    try:
        sh = conectar_google().open("Gestion_Magallan")
        df_p = pd.DataFrame(sh.worksheet("Proyectos").get_all_records())
        df_l = pd.DataFrame(sh.worksheet("Logistica").get_all_records())
        df_c = pd.DataFrame(sh.worksheet("Chat_Interno").get_all_records())
        # Normalización automática de columnas
        for df in [df_p, df_l, df_c]:
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        return sh, df_p, df_l, df_c
    except Exception as e:
        st.error(f"⚠️ Error al sincronizar: {e}")
        return None, None, None, None

sh, df_p, df_l, df_c = cargar_datos()

# 3. FUNCIÓN GENERADORA DE PDF
def generar_pdf(datos_obra):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "REPORTE DE ESTADO - GRUPO MAGALLAN", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    pdf.cell(200, 10, f"Presupuesto: #{datos_obra['nro_ppto']}", ln=True)
    pdf.cell(200, 10, f"Cliente: {datos_obra['cliente']}", ln=True)
    pdf.cell(200, 10, f"Estado Actual: {datos_obra['estado_fabricacion']}", ln=True)
    pdf.cell(200, 10, f"Fecha Entrega: {datos_obra['fecha_entrega']}", ln=True)
    pdf.ln(5)
    pdf.cell(200, 10, f"Saldo Pendiente: $ {float(datos_obra['monto_total_ars']) - float(datos_obra['pagado_ars']):,.2f}", ln=True)
    return pdf.output(dest="S").encode("latin-1")

# --- NAVEGACIÓN ---
st.sidebar.title("🏗️ Grupo Magallan")
menu = st.sidebar.radio("Módulos", ["📈 Dashboard", "📝 Proyectos", "🚛 Logística & Chat"])

if df_p is not None:
    # --- DASHBOARD ---
    if menu == "📈 Dashboard":
        st.header("📊 Tablero de Control Operativo")
        hoy = datetime.now().date()
        df_p['fecha_dt'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
        atrasos = df_p[(df_p['fecha_dt'] < hoy) & (df_p['estado_fabricacion'] != "Entregado")]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Obras Activas", len(df_p))
        c2.metric("Vencidas ⚠️", len(atrasados), delta=len(atrasados), delta_color="inverse")
        c3.metric("Recaudación", f"$ {pd.to_numeric(df_p['pagado_ars']).sum():,.0f}")
        
        if not atrasados.empty:
            st.subheader("🚨 Prioridades")
            for _, r in atrasados.iterrows():
                st.markdown(f"<div class='atraso-card'><strong>{r['cliente']}</strong> - Vencido el {r['fecha_entrega']}</div>", unsafe_allow_html=True)

    # --- PROYECTOS (Carga en Pesos Directa) ---
    elif menu == "📝 Proyectos":
        t1, t2 = st.tabs(["🆕 Alta de Obra", "✏️ Editar y PDF"])
        
        with t1:
            with st.form("nueva", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n_ppto = c1.number_input("Nro Presupuesto", step=1)
                n_cli = c1.text_input("Cliente")
                n_monto = c2.number_input("Monto Total (ARS)", min_value=0.0)
                n_ent = c2.date_input("Fecha Entrega")
                if st.form_submit_button("Guardar"):
                    sh.worksheet("Proyectos").append_row([n_ppto, n_cli, "Esperando", str(datetime.now().date()), str(n_ent), n_monto, 0, "", ""])
                    sh.worksheet("Logistica").append_row([n_ppto, "", str(n_ent), "Pendiente", ""])
                    st.success("✅ Obra registrada exitosamente.")
                    st.rerun()

        with t2:
            sel = st.selectbox("Seleccionar Presupuesto:", df_p['nro_ppto'].unique())
            obra = df_p[df_p['nro_ppto'] == sel].iloc[0]
            
            with st.form("edit"):
                c1, c2 = st.columns(2)
                nuevo_est = c1.selectbox("Estado", ["Esperando", "Preparacion", "Terminado", "Entregado"], 
                                         index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(obra['estado_fabricacion']))
                nuevo_pago = c1.number_input("Actualizar Pagado (ARS)", value=float(obra['pagado_ars']))
                if st.form_submit_button("Actualizar"):
                    idx = df_p[df_p['nro_ppto'] == sel].index[0] + 2
                    sh.worksheet("Proyectos").update_cell(idx, 3, nuevo_est)
                    sh.worksheet("Proyectos").update_cell(idx, 7, nuevo_pago)
                    st.success("Actualizado.")
                    st.rerun()
            
            # Botón de PDF
            pdf_bytes = generar_pdf(obra)
            st.download_button(label="📥 Descargar Reporte PDF", data=pdf_bytes, file_name=f"Obra_{sel}.pdf", mime="application/pdf")

    # --- LOGÍSTICA & CHAT ---
    elif menu == "🚛 Logística & Chat":
        sel_ppto = st.sidebar.selectbox("Obra:", df_p['nro_ppto'].unique())
        tab_l, tab_c = st.tabs(["📦 Logística", "💬 Chat"])
        
        with tab_l:
            idx_l = df_l[df_l['nro_ppto'].astype(str) == str(sel_ppto)].index
            if not idx_l.empty:
                with st.form("log"):
                    tecs = st.text_input("Instaladores", value=df_l.loc[idx_l[0], 'tecnicos'])
                    if st.form_submit_button("Guardar"):
                        sh.worksheet("Logistica").update_cell(int(idx_l[0])+2, 2, tecs)
                        st.success("Guardado.")
            
        with tab_c:
            msgs = df_c[df_c['nro_ppto'].astype(str) == str(sel_ppto)]
            for _, m in msgs.iterrows():
                with st.chat_message("user"):
                    st.write(f"*{m['usuario']}*: {m['mensaje']}")
            with st.form("chat", clear_on_submit=True):
                msg = st.text_area("Escribir mensaje...")
                if st.form_submit_button("Enviar"):
                    sh.worksheet("Chat_Interno").append_row([sel_ppto, "Admin", datetime.now().strftime("%H:%M"), msg])
                    st.rerun()