import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF

# 1. CONFIGURACIÓN E IDENTIDAD VISUAL
st.set_page_config(page_title="Grupo Magallan | Gestión de Cortinas", layout="wide", page_icon="🏗️")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-top: 4px solid #1E3A8A; }
    .atraso-card { background-color: #FEF2F2; border-left: 5px solid #EF4444; padding: 15px; border-radius: 8px; margin-bottom: 10px; color: #991B1B; }
    .proximo-card { background-color: #FFFBEB; border-left: 5px solid #F59E0B; padding: 15px; border-radius: 8px; margin-bottom: 10px; color: #92400E; }
    .historial-item { font-size: 0.85rem; border-bottom: 1px solid #eee; padding: 5px 0; }
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
        
        # Cargar Historial (si no existe, lo manejamos)
        try:
            df_h = pd.DataFrame(sh.worksheet("Historial").get_all_records())
        except:
            df_h = pd.DataFrame(columns=['nro_ppto', 'fecha_hora', 'usuario', 'accion'])

        for df in [df_p, df_l, df_c, df_h]:
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
            
        return sh, df_p, df_l, df_c, df_h
    except Exception as e:
        st.error(f"⚠️ Error al leer datos: {e}")
        return None, None, None, None, None

sh, df_p, df_l, df_c, df_h = cargar_datos()

# 3. FUNCIONES AUXILIARES
def registrar_historial(nro_ppto, usuario, accion):
    try:
        ws_h = sh.worksheet("Historial")
        ws_h.append_row([str(nro_ppto), datetime.now().strftime("%d/%m/%Y %H:%M"), usuario, accion])
    except:
        pass # Evita que la app se trabe si no existe la pestaña

def generar_pdf(cortina):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(30, 58, 138) 
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 20, "GRUPO MAGALLAN", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 5, "Reporte Detallado de Cortina", ln=True, align="C")
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(25)
    pdf.set_font("Arial", "B", 12); pdf.set_fill_color(240, 240, 240)
    pdf.cell(190, 10, f" DATOS TÉCNICOS: #{cortina['nro_ppto']}", ln=True, fill=True)
    pdf.set_font("Arial", "", 11); pdf.ln(2)
    pdf.cell(95, 8, f"Cliente: {cortina['cliente']}")
    pdf.cell(95, 8, f"Entrega: {cortina['fecha_entrega']}", ln=True, align="R")
    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, " MATERIALES PENDIENTES", ln=True, fill=True)
    pdf.set_font("Arial", "I", 11); pdf.ln(2)
    pdf.multi_cell(0, 8, str(cortina.get('materiales_pendientes', 'Sin registrar')))
    
    pdf.ln(10)
    total, pagado = float(cortina['monto_total_ars']), float(cortina['pagado_ars'])
    pdf.set_font("Arial", "B", 12); pdf.cell(190, 10, " RESUMEN FINANCIERO", ln=True, fill=True)
    pdf.set_font("Arial", "", 11); pdf.cell(100, 8, f"Total: $ {total:,.2f}"); pdf.cell(90, 8, f"Pagado: $ {pagado:,.2f}", ln=True, align="R")
    pdf.set_text_color(190, 0, 0); pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 12, f"SALDO PENDIENTE: $ {total-pagado:,.2f}", ln=True, align="R")
    
    return pdf.output(dest="S").encode("latin-1")

# --- NAVEGACIÓN ---
st.sidebar.title("🏗️ Grupo Magallan")
user_name = st.sidebar.text_input("Tu Nombre (para historial):", value="Admin")
menu = st.sidebar.radio("Ir a:", ["📈 Dashboard", "📝 Gestión de Cortinas", "🚛 Logística & Chat"])

if df_p is not None:
    # --- DASHBOARD ---
    if menu == "📈 Dashboard":
        st.header("📊 Tablero de Control Operativo")
        hoy = datetime.now().date()
        df_p['fecha_dt'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
        atrasados = df_p[(df_p['fecha_dt'] < hoy) & (df_p['estado_fabricacion'] != "Entregado")]
        proximos = df_p[(df_p['fecha_dt'] >= hoy) & (df_p['fecha_dt'] <= hoy + timedelta(days=5)) & (df_p['estado_fabricacion'] != "Entregado")]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Cortinas Activas", len(df_p[df_p['estado_fabricacion'] != "Entregado"]))
        c2.metric("Vencidas ⚠️", len(atrasados), delta=len(atrasados), delta_color="inverse")
        c3.metric("Por Vencer (5 días)", len(proximos))
        
        if not atrasados.empty:
            st.subheader("🚨 Vencidas")
            for _, r in atrasados.iterrows():
                st.markdown(f"<div class='atraso-card'><strong>{r['cliente']}</strong> - Ppto #{r['nro_ppto']} (Vencido)</div>", unsafe_allow_html=True)
        
        if not proximos.empty:
            st.subheader("⏳ Próximos 5 días")
            for _, r in proximos.iterrows():
                st.markdown(f"<div class='proximo-card'><strong>{r['cliente']}</strong> - Entrega: {r['fecha_entrega']}</div>", unsafe_allow_html=True)

    # --- GESTIÓN DE CORTINAS ---
    elif menu == "📝 Gestión de Cortinas":
        t1, t2 = st.tabs(["🆕 Alta", "✏️ Editar e Historial"])
        
        with t1:
            with st.form("alta", clear_on_submit=True):
                c1, c2 = st.columns(2)
                p_nro = c1.number_input("Nro Presupuesto", step=1)
                p_cli = c1.text_input("Cliente")
                p_mon = c2.number_input("Monto ($)", min_value=0.0)
                p_fec = c2.date_input("Fecha Entrega")
                p_mat = st.text_area("Materiales Pendientes")
                if st.form_submit_button("Guardar"):
                    sh.worksheet("Proyectos").append_row([p_nro, p_cli, "Esperando", str(hoy), str(p_fec), p_mon, 0, "", "", p_mat])
                    sh.worksheet("Logistica").append_row([p_nro, "", str(p_fec), "Pendiente", ""])
                    registrar_historial(p_nro, user_name, "Creación de cortina")
                    st.success("✅ Cortina guardada.")
                    st.rerun()

        with t2:
            sel = st.selectbox("Seleccione Cortina:", df_p['nro_ppto'].unique())
            datos = df_p[df_p['nro_ppto'] == sel].iloc[0]
            
            c_ed, c_hi = st.columns([2, 1])
            
            with c_ed:
                with st.form("edit"):
                    est = st.selectbox("Estado", ["Esperando", "Preparacion", "Terminado", "Entregado"], index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(datos['estado_fabricacion']))
                    pag = st.number_input("Pagado ($)", value=float(datos['pagado_ars']))
                    mat = st.text_area("Materiales", value=datos.get('materiales_pendientes', ''))
                    if st.form_submit_button("Actualizar"):
                        idx = df_p[df_p['nro_ppto'] == sel].index[0] + 2
                        ws_p = sh.worksheet("Proyectos")
                        ws_p.update_cell(idx, 3, est); ws_p.update_cell(idx, 7, pag); ws_p.update_cell(idx, 10, mat)
                        registrar_historial(sel, user_name, f"Cambio Estado: {est} | Pago: {pag}")
                        st.success("✅ Actualizado.")
                        st.rerun()
                st.download_button(label="📥 PDF", data=generar_pdf(datos), file_name=f"Cortina_{sel}.pdf")

            with c_hi:
                st.subheader("📜 Historial")
                h_filtrado = df_h[df_h['nro_ppto'].astype(str) == str(sel)].sort_values(by='fecha_hora', ascending=False)
                if not h_filtrado.empty:
                    for _, h in h_filtrado.iterrows():
                        st.markdown(f"<div class='historial-item'><strong>{h['fecha_hora']}</strong> - {h['usuario']}:<br>{h['accion']}</div>", unsafe_allow_html=True)
                else:
                    st.write("Sin registros previos.")

    # --- LOGÍSTICA ---
    elif menu == "🚛 Logística & Chat":
        sel_ppto = st.sidebar.selectbox("Cortina:", df_p['nro_ppto'].unique())
        tab_l, tab_c = st.tabs(["📦 Logística", "💬 Chat"])
        
        with tab_l:
            idx_l = df_l[df_l['nro_ppto'].astype(str) == str(sel_ppto)].index
            if not idx_l.empty:
                with st.form("log"):
                    tcs = st.text_input("Instaladores", value=df_l.loc[idx_l[0], 'tecnicos'])
                    if st.form_submit_button("Guardar"):
                        sh.worksheet("Logistica").update_cell(int(idx_l[0])+2, 2, tcs)
                        registrar_historial(sel_ppto, user_name, f"Asignación instaladores: {tcs}")
                        st.success("Logística guardada.")