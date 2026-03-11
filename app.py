import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. Configuración y Estilo
st.set_page_config(page_title="Grupo Magallan | Gestión 360", layout="wide")

# Estilo personalizado para las métricas de alerta
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 28px; }
    .atrasado { color: #FF4B4B; font-weight: bold; }
    .al día { color: #00CC96; }
    </style>
    """, unsafe_allow_html=True)

# 2. Conexión a Google Sheets
@st.cache_resource
def conectar_google():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

client = conectar_google()
SHEET_NAME = "Gestion_Magallan"

def cargar_datos():
    sh = client.open(SHEET_NAME)
    df_p = pd.DataFrame(sh.worksheet("Proyectos").get_all_records())
    df_l = pd.DataFrame(sh.worksheet("Logistica").get_all_records())
    df_c = pd.DataFrame(sh.worksheet("Chat_Interno").get_all_records())
    return sh, df_p, df_l, df_c

sh, df_p, df_l, df_c = cargar_datos()

# --- NAVEGACIÓN LATERAL ---
st.sidebar.title("🏗️ Grupo Magallan")
menu = st.sidebar.radio("Navegación", ["📈 Tablero de Control", "🏗️ Gestión de Obras", "🚚 Logística y Chat"])

# --- SECCIÓN 1: TABLERO DE CONTROL (Smart Dashboard) ---
if menu == "📈 Tablero de Control":
    st.header("📈 Tablero de Control Inteligente")
    
    if not df_p.empty:
        # Cálculos para el tablero
        hoy = datetime.now().date()
        df_p['Fecha_Entrega_DT'] = pd.to_datetime(df_p['Fecha_Entrega'], errors='coerce').dt.date
        
        obras_atrasadas = df_p[(df_p['Fecha_Entrega_DT'] < hoy) & (df_p['Estado_Fabricacion'] != "Entregado")]
        total_deuda = df_p['Monto_Total_Ars'].sum() - df_p['Pagado_Ars'].sum()
        
        # Fila de métricas principales
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Obras Totales", len(df_p))
        c2.metric("Atrasadas ⚠️", len(obras_atrasadas), delta=len(obras_atrasadas), delta_color="inverse")
        c3.metric("Saldo por Cobrar", f"$ {total_deuda:,.2f}", delta="Pendiente")
        c4.metric("En Planta", len(df_p[df_p['Estado_Fabricacion'] == "Preparacion"]))

        st.divider()

        # Tabla de Alertas Prioritarias
        st.subheader("🚨 Prioridades y Alertas de Entrega")
        if not obras_atrasadas.empty:
            st.error(f"Atención: Tienes {len(obras_atrasadas)} obras fuera de fecha de entrega.")
            st.dataframe(obras_atrasadas[['Nro_Ppto', 'Cliente', 'Fecha_Entrega', 'Estado_Fabricacion']], use_container_width=True)
        else:
            st.success("✅ Todas las entregas están programadas a tiempo.")

# --- SECCIÓN 2: GESTIÓN DE OBRAS (Nuevo y Editar) ---
elif menu == "🏗️ Gestión de Obras":
    sub_menu = st.tabs(["🆕 Nuevo Presupuesto", "✏️ Editar Existente"])
    
    with sub_menu[0]:
        st.subheader("Cargar Nuevo Presupuesto")
        with st.form("nuevo_ppto", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                n_ppto = st.number_input("Nro Presupuesto", step=1)
                n_cliente = st.text_input("Cliente")
                n_iva = st.selectbox("IVA", ["Sin IVA", "Con IVA (21%)"])
            with c2:
                n_total = st.number_input("Monto Total", min_value=0.0)
                n_pago = st.number_input("Anticipo", min_value=0.0)
                n_entrega = st.date_input("Fecha Prometida Entrega")
            
            if st.form_submit_button("Registrar en Sistema"):
                nueva_fila = [n_ppto, n_cliente, "Esperando", str(datetime.now().date()), str(n_entrega), n_total, n_pago, n_iva, ""]
                sh.worksheet("Proyectos").append_row(nueva_fila)
                # Crear fila vacía en Logística para evitar errores
                sh.worksheet("Logistica").append_row([n_ppto, "", str(n_entrega), "Pendiente", "", ""])
                st.success("Registrado correctamente.")

    with sub_menu[1]:
        ppto_sel = st.selectbox("Seleccione presupuesto para editar", df_p['Nro_Ppto'].unique())
        idx = df_p[df_p['Nro_Ppto'] == ppto_sel].index[0]
        datos = df_p.iloc[idx]
        
        with st.form("editar_ppto"):
            col1, col2 = st.columns(2)
            est = col1.selectbox("Estado", ["Esperando", "Preparacion", "Terminado", "Entregado"], 
                               index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(datos['Estado_Fabricacion']) if datos['Estado_Fabricacion'] in ["Esperando", "Preparacion", "Terminado", "Entregado"] else 0)
            pag = col1.number_input("Monto Pagado Actual", value=float(datos['Pagado_Ars']))
            notas = col2.text_area("Notas de Planta", value=datos.get('Notas_Planta', ''))
            
            if st.form_submit_button("Actualizar"):
                ws = sh.worksheet("Proyectos")
                fila = int(idx) + 2
                ws.update_cell(fila, 3, est)
                ws.update_cell(fila, 7, pag)
                ws.update_cell(fila, 9, notas)
                st.success("Actualizado.")
                st.rerun()

# --- SECCIÓN 3: LOGÍSTICA Y CHAT ---
elif menu == "🚚 Logística y Chat":
    ppto_sel = st.sidebar.selectbox("Obra:", df_p['Nro_Ppto'].unique())
    t1, t2 = st.tabs(["📦 Instalación", "💬 Chat Interno"])
    
    with t1:
        idx_l = df_l[df_l['Nro_Ppto'] == ppto_sel].index
        if not idx_l.empty:
            d_l = df_l.iloc[idx_l[0]]
            with st.form("form_l"):
                tecs = st.text_input("Técnicos", value=d_l['Tecnicos'])
                link = st.text_input("Link Fotos (Drive)", value=d_l['Url_Fotos'])
                if st.form_submit_button("Guardar Logística"):
                    ws_l = sh.worksheet("Logistica")
                    ws_l.update_cell(int(idx_l[0])+2, 2, tecs)
                    ws_l.update_cell(int(idx_l[0])+2, 5, link)
                    st.success("Guardado.")
        
    with t2:
        # Mostrar Chat
        mensajes = df_c[df_c['Nro_Ppto'].astype(str) == str(ppto_sel)]
        for _, m in mensajes.iterrows():
            with st.chat_message("user"):
                st.write(f"*{m['Usuario']}*: {m['Mensaje']}")
        
        with st.form("nuevo_msg", clear_on_submit=True):
            nom = st.text_input("Nombre", value="Admin")
            txt = st.text_area("Escribir mensaje...")
            if st.form_submit_button("Enviar"):
                sh.worksheet("Chat_Interno").append_row([ppto_sel, nom, datetime.now().strftime("%H:%M"), txt])
                st.rerun()