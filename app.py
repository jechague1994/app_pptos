import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF

# 1. CONFIGURACIÓN Y ESTILO DE ALTA VISIBILIDAD
st.set_page_config(page_title="Magallan | Gestión Total", layout="wide")

st.markdown("""
    <style>
    html, body, [class*="st-"] { font-size: 1.25rem !important; }
    label { font-size: 1.6rem !important; font-weight: bold !important; color: #1E3A8A !important; }
    [data-testid="stMetricValue"] { font-size: 4rem !important; font-weight: 800 !important; }
    
    .atraso-card { 
        background-color: #FEF2F2; border-left: 12px solid #EF4444; 
        padding: 25px; border-radius: 15px; margin-bottom: 20px; 
        color: #991B1B; font-size: 1.9rem !important; font-weight: bold;
    }
    .proximo-card { 
        background-color: #FFFBEB; border-left: 12px solid #F59E0B; 
        padding: 25px; border-radius: 15px; margin-bottom: 20px; 
        color: #92400E; font-size: 1.9rem !important; font-weight: bold;
    }

    .stButton>button {
        width: 100%; height: 90px; font-size: 2rem !important;
        background-color: #1E3A8A !important; color: white !important;
        border-radius: 15px !important; margin-top: 10px;
    }
    
    .historial-item { font-size: 1.1rem; border-bottom: 2px solid #eee; padding: 12px 0; }
    </style>
    """, unsafe_allow_html=True)

# 2. CONEXIÓN Y CARGA PROTEGIDA
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
        def limpiar_df(nombre_hoja):
            try:
                data = sh.worksheet(nombre_hoja).get_all_records()
                df = pd.DataFrame(data)
                df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
                return df
            except: return pd.DataFrame()
        return sh, limpiar_df("Proyectos"), limpiar_df("Logistica"), limpiar_df("Chat_Interno"), limpiar_df("Historial")
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
        return None, None, None, None, None

sh, df_p, df_l, df_c, df_h = cargar_datos()

# 3. GENERADOR DE PDF
def generar_pdf(cortina):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(30, 58, 138); pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", "B", 22)
    pdf.cell(0, 20, "GRUPO MAGALLAN", ln=True, align="C")
    pdf.set_text_color(0, 0, 0); pdf.ln(25)
    pdf.set_font("Arial", "B", 14); pdf.set_fill_color(240, 240, 240)
    pdf.cell(190, 10, f" DETALLES DE CORTINA: #{cortina.get('nro_ppto', 'N/A')}", ln=True, fill=True)
    pdf.set_font("Arial", "", 12); pdf.ln(5)
    pdf.cell(0, 10, f"Cliente: {cortina.get('cliente', 'S/D')}", ln=True)
    pdf.cell(0, 10, f"Entrega: {cortina.get('fecha_entrega', 'S/D')}", ln=True)
    pdf.ln(5); pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, " MATERIALES PENDIENTES:", ln=True, fill=True)
    pdf.set_font("Arial", "I", 12); pdf.multi_cell(0, 10, str(cortina.get('materiales_pendientes', 'Ninguno')))
    return pdf.output(dest="S").encode("latin-1")

# --- NAVEGACIÓN ---
st.sidebar.title("🏗️ MAGALLAN")
user_name = st.sidebar.text_input("Operador:", value="Admin")
menu = st.sidebar.radio("MENÚ", ["📈 TABLERO", "📝 GESTIÓN", "🚛 LOGÍSTICA"], index=0)

if df_p is not None and not df_p.empty:
    # --- TABLERO ---
    if menu == "📈 TABLERO":
        st.title("📊 Control de Producción")
        hoy = datetime.now().date()
        df_p['fecha_dt'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
        
        atrasados = df_p[(df_p['fecha_dt'] < hoy) & (df_p['estado_fabricacion'] != "Entregado")]
        proximos = df_p[(df_p['fecha_dt'] >= hoy) & (df_p['fecha_dt'] <= hoy + timedelta(days=5)) & (df_p['estado_fabricacion'] != "Entregado")]

        c1, c2 = st.columns(2)
        c1.metric("VENCIDAS 🚨", len(atrasados))
        c2.metric("PRÓXIMAS ⏳", len(proximos))

        if not atrasados.empty:
            st.markdown("## 🚨 VENCIDAS")
            for _, r in atrasados.iterrows():
                st.markdown(f"<div class='atraso-card'>{r.get('cliente','S/D')} - #{r.get('nro_ppto','')}<br><small>Vencía: {r.get('fecha_entrega','')}</small></div>", unsafe_allow_html=True)

        if not proximos.empty:
            st.markdown("## ⏳ ENTREGAS ESTA SEMANA")
            for _, r in proximos.iterrows():
                st.markdown(f"<div class='proximo-card'>{r.get('cliente','S/D')} - #{r.get('nro_ppto','')}<br><small>Entrega: {r.get('fecha_entrega','')}</small></div>", unsafe_allow_html=True)

    # --- GESTIÓN ---
    elif menu == "📝 GESTIÓN":
        st.title("📝 Gestión de Cortinas")
        t1, t2 = st.tabs(["🆕 Nueva Cortina", "✏️ Editar / Buscar"])
        
        with t1:
            with st.form("alta_gigante"):
                c1, c2 = st.columns(2)
                p_nro = c1.number_input("Nro Presupuesto", step=1)
                p_cli = c1.text_input("Cliente")
                p_mon = c2.number_input("Monto ($)", min_value=0.0)
                p_fec = c2.date_input("Fecha Entrega")
                p_mat = st.text_area("Materiales Pendientes")
                if st.form_submit_button("GUARDAR NUEVA CORTINA"):
                    sh.worksheet("Proyectos").append_row([p_nro, p_cli, "Esperando", str(datetime.now().date()), str(p_fec), p_mon, 0, "", "", p_mat])
                    sh.worksheet("Logistica").append_row([p_nro, "", str(p_fec), "Pendiente", ""])
                    sh.worksheet("Historial").append_row([str(p_nro), datetime.now().strftime("%d/%m %H:%M"), user_name, "Alta de cortina"])
                    st.success("✅ GUARDADO")
                    st.rerun()

        with t2:
            # BUSCADOR MEJORADO: Por número o Nombre
            df_p['display_name'] = df_p['nro_ppto'].astype(str) + " - " + df_p['cliente'].astype(str)
            sel_display = st.selectbox("BUSCAR POR PPTO O CLIENTE:", df_p['display_name'].unique())
            sel = sel_display.split(" - ")[0]
            
            datos = df_p[df_p['nro_ppto'].astype(str) == str(sel)].iloc[0]
            
            c_ed, c_hi = st.columns([1.5, 1])
            with c_ed:
                with st.form("edicion"):
                    st.markdown(f"### Editando: {datos['cliente']}")
                    est_op = ["Esperando", "Preparacion", "Terminado", "Entregado"]
                    idx_est = est_op.index(datos['estado_fabricacion']) if datos['estado_fabricacion'] in est_op else 0
                    nuevo_est = st.selectbox("ESTADO ACTUAL:", est_op, index=idx_est)
                    nuevo_mat = st.text_area("ACTUALIZAR MATERIALES:", value=str(datos.get('materiales_pendientes', '')))
                    if st.form_submit_button("ACTUALIZAR"):
                        idx_row = df_p[df_p['nro_ppto'].astype(str) == str(sel)].index[0] + 2
                        ws = sh.worksheet("Proyectos")
                        ws.update_cell(idx_row, 3, nuevo_est)
                        ws.update_cell(idx_row, 10, nuevo_mat)
                        sh.worksheet("Historial").append_row([str(sel), datetime.now().strftime("%d/%m %H:%M"), user_name, f"Cambio a {nuevo_est}"])
                        st.success("✅ ACTUALIZADO")
                        st.rerun()
                st.download_button("📥 DESCARGAR PDF", data=generar_pdf(datos), file_name=f"Cortina_{sel}.pdf")

            with c_hi:
                st.subheader("📜 Historial de esta Cortina")
                if not df_h.empty:
                    h_f = df_h[df_h['nro_ppto'].astype(str) == str(sel)].sort_values(by='fecha_hora', ascending=False)
                    for _, h in h_f.iterrows():
                        st.markdown(f"<div class='historial-item'><strong>{h.get('fecha_hora','')}</strong>: {h.get('accion','')}</div>", unsafe_allow_html=True)

    # --- LOGÍSTICA ---
    elif menu == "🚛 LOGÍSTICA":
        st.title("🚛 Logística e Instalaciones")
        df_p['display_name'] = df_p['nro_ppto'].astype(str) + " - " + df_p['cliente'].astype(str)
        sel_l_display = st.selectbox("SELECCIONE CORTINA:", df_p['display_name'].unique())
        sel_l = sel_l_display.split(" - ")[0]
        
        idx_l = df_l[df_l['nro_ppto'].astype(str) == str(sel_l)].index
        if not idx_l.empty:
            with st.form("log_gigante"):
                inst = st.text_input("INSTALADORES ASIGNADOS:", value=df_l.loc[idx_l[0], 'tecnicos'])
                if st.form_submit_button("GUARDAR LOGÍSTICA"):
                    sh.worksheet("Logistica").update_cell(int(idx_l[0])+2, 2, inst)
                    sh.worksheet("Historial").append_row([str(sel_l), datetime.now().strftime("%d/%m %H:%M"), user_name, f"Instaladores: {inst}"])
                    st.success("✅ LOGÍSTICA ACTUALIZADA")