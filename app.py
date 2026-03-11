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

# 2. CONEXIÓN Y CARGA DE DATOS (CON LIMPIEZA AUTOMÁTICA)
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
        
        def get_df(nombre_hoja):
            try:
                data = sh.worksheet(nombre_hoja).get_all_records()
                df = pd.DataFrame(data)
                # LIMPIEZA CRÍTICA: Quita espacios, pasa a minúsculas y reemplaza espacios por guiones bajos
                df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
                return df
            except:
                return pd.DataFrame()

        df_p = get_df("Proyectos")
        df_l = get_df("Logistica")
        df_c = get_df("Chat_Interno")
        df_h = get_df("Historial")
            
        return sh, df_p, df_l, df_c, df_h
    except Exception as e:
        st.error(f"⚠️ Error general al leer datos: {e}")
        return None, None, None, None, None

sh, df_p, df_l, df_c, df_h = cargar_datos()

# 3. FUNCIONES DE APOYO
def registrar_historial(nro_ppto, usuario, accion):
    try:
        sh.worksheet("Historial").append_row([str(nro_ppto), datetime.now().strftime("%d/%m/%Y %H:%M"), usuario, accion])
    except:
        pass

def generar_pdf(cortina):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(30, 58, 138); pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 20, "GRUPO MAGALLAN", ln=True, align="C")
    pdf.set_text_color(0, 0, 0); pdf.ln(25)
    pdf.set_font("Arial", "B", 12); pdf.set_fill_color(240, 240, 240)
    pdf.cell(190, 10, f" DETALLES DE CORTINA: #{cortina.get('nro_ppto', 'N/A')}", ln=True, fill=True)
    pdf.set_font("Arial", "", 11); pdf.ln(2)
    pdf.cell(95, 8, f"Cliente: {cortina.get('cliente', 'S/D')}")
    pdf.cell(95, 8, f"Entrega: {cortina.get('fecha_entrega', 'S/D')}", ln=True, align="R")
    
    pdf.ln(5); pdf.set_font("Arial", "B", 12); pdf.cell(190, 10, " MATERIALES PENDIENTES", ln=True, fill=True)
    pdf.set_font("Arial", "I", 11); pdf.ln(2)
    pdf.multi_cell(0, 8, str(cortina.get('materiales_pendientes', 'Sin registrar')))
    
    return pdf.output(dest="S").encode("latin-1")

# --- NAVEGACIÓN ---
st.sidebar.title("🏗️ Grupo Magallan")
user_name = st.sidebar.text_input("Tu Nombre:", value="Admin")
menu = st.sidebar.radio("Ir a:", ["📈 Dashboard", "📝 Gestión de Cortinas", "🚛 Logística & Chat"])

if df_p is not None and not df_p.empty:
    # --- DASHBOARD (SOLUCIÓN AL KEYERROR DE FECHA) ---
    if menu == "📈 Dashboard":
        st.header("📊 Tablero de Control")
        hoy = datetime.now().date()
        
        # Manejo seguro de fechas para evitar errores de años extraños
        df_p['fecha_dt'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
        
        atrasados = df_p[(df_p['fecha_dt'] < hoy) & (df_p['estado_fabricacion'] != "Entregado")]
        proximos = df_p[(df_p['fecha_dt'] >= hoy) & (df_p['fecha_dt'] <= hoy + timedelta(days=5)) & (df_p['estado_fabricacion'] != "Entregado")]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Cortinas Activas", len(df_p[df_p['estado_fabricacion'] != "Entregado"]))
        c2.metric("Vencidas ⚠️", len(atrasados))
        c3.metric("Próximos 5 días", len(proximos))
        
        if not atrasados.empty:
            st.subheader("🚨 Entregas Vencidas")
            for _, r in atrasados.iterrows():
                st.markdown(f"<div class='atraso-card'><strong>{r.get('cliente','S/D')}</strong> - #{r.get('nro_ppto','')} (Vencido)</div>", unsafe_allow_html=True)
        
        if not proximos.empty:
            st.subheader("⏳ A entregar pronto (Alerta 5 días)")
            for _, r in proximos.iterrows():
                st.markdown(f"<div class='proximo-card'><strong>{r.get('cliente','S/D')}</strong> - Entrega: {r.get('fecha_entrega','')}</div>", unsafe_allow_html=True)

    # --- GESTIÓN DE CORTINAS ---
    elif menu == "📝 Gestión de Cortinas":
        t1, t2 = st.tabs(["🆕 Alta", "✏️ Editar e Historial"])
        
        with t1:
            with st.form("alta", clear_on_submit=True):
                c1, c2 = st.columns(2)
                p_nro = c1.number_input("Nro Presupuesto", step=1)
                p_cli = c1.text_input("Cliente")
                p_mon = c2.number_input("Monto Final ($)", min_value=0.0)
                p_fec = c2.date_input("Fecha Entrega")
                p_mat = st.text_area("Materiales Pendientes")
                if st.form_submit_button("Guardar Cortina"):
                    sh.worksheet("Proyectos").append_row([p_nro, p_cli, "Esperando", str(datetime.now().date()), str(p_fec), p_mon, 0, "", "", p_mat])
                    sh.worksheet("Logistica").append_row([p_nro, "", str(p_fec), "Pendiente", ""])
                    registrar_historial(p_nro, user_name, "Alta de cortina")
                    st.success("Guardado correctamente.")
                    st.rerun()

        with t2:
            opciones = df_p['nro_ppto'].unique()
            sel = st.selectbox("Seleccione Cortina:", opciones)
            datos = df_p[df_p['nro_ppto'] == sel].iloc[0]
            
            col_ed, col_hi = st.columns([2, 1])
            with col_ed:
                with st.form("edit"):
                    est_list = ["Esperando", "Preparacion", "Terminado", "Entregado"]
                    # Buscador de índice seguro para evitar errores si el estado en Excel está mal escrito
                    idx_est = est_list.index(datos['estado_fabricacion']) if datos['estado_fabricacion'] in est_list else 0
                    
                    nuevo_est = st.selectbox("Estado", est_list, index=idx_est)
                    nuevo_pag = st.number_input("Monto Pagado ($)", value=float(datos.get('pagado_ars', 0)))
                    nuevo_mat = st.text_area("Materiales", value=str(datos.get('materiales_pendientes', '')))
                    
                    if st.form_submit_button("Actualizar Todo"):
                        row_idx = df_p[df_p['nro_ppto'] == sel].index[0] + 2
                        ws = sh.worksheet("Proyectos")
                        ws.update_cell(row_idx, 3, nuevo_est)
                        ws.update_cell(row_idx, 7, nuevo_pag)
                        ws.update_cell(row_idx, 10, nuevo_mat)
                        registrar_historial(sel, user_name, f"Actualización: {nuevo_est}")
                        st.success("✅ Datos actualizados.")
                        st.rerun()
                st.download_button("📥 Descargar Reporte PDF", data=generar_pdf(datos), file_name=f"Cortina_{sel}.pdf")

            with col_hi:
                st.subheader("📜 Historial")
                if not df_h.empty:
                    h_f = df_h[df_h['nro_ppto'].astype(str) == str(sel)].sort_values(by='fecha_hora', ascending=False)
                    for _, h in h_f.iterrows():
                        st.markdown(f"<div class='historial-item'><strong>{h.get('fecha_hora','')}</strong>: {h.get('accion','')}</div>", unsafe_allow_html=True)

    # --- LOGÍSTICA & CHAT (CORRECCIÓN KEYERROR NRO_PPTO) ---
    elif menu == "🚛 Logística & Chat":
        sel_ppto = st.sidebar.selectbox("Cortina:", df_p['nro_ppto'].unique())
        tab_l, tab_c = st.tabs(["📦 Logística", "💬 Chat Interno"])
        
        with tab_l:
            # Uso de astype(str) para evitar el error de comparación entre números y strings
            idx_l = df_l[df_l['nro_ppto'].astype(str) == str(sel_ppto)].index
            if not idx_l.empty:
                with st.form("log"):
                    tcs = st.text_input("Instaladores", value=df_l.loc[idx_l[0], 'tecnicos'])
                    if st.form_submit_button("Guardar Instaladores"):
                        sh.worksheet("Logistica").update_cell(int(idx_l[0])+2, 2, tcs)
                        st.success("Logística actualizada.")
        
        with tab_c:
            mensajes = df_c[df_c['nro_ppto'].astype(str) == str(sel_ppto)]
            for _, m in mensajes.iterrows():
                with st.chat_message("user"):
                    st.write(f"*{m.get('usuario','S/D')}*: {m.get('mensaje','')}")
            
            with st.form("chat", clear_on_submit=True):
                msg = st.text_area("Nuevo mensaje...")
                if st.form_submit_button("Enviar"):
                    sh.worksheet("Chat_Interno").append_row([str(sel_ppto), user_name, datetime.now().strftime("%H:%M"), msg])
                    st.rerun()