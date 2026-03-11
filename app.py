import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Grupo Magallan | Gestión 360", layout="wide")

# 2. CONEXIÓN A GOOGLE SHEETS
@st.cache_resource
def conectar_google():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"❌ Error de configuración: {e}")
        st.stop()

client = conectar_google()
SHEET_NAME = "Gestion_Magallan"

# 3. CARGA Y NORMALIZACIÓN DE DATOS (Soluciona los KeyErrors)
def cargar_datos():
    try:
        sh = client.open(SHEET_NAME)
        # Cargamos las 3 pestañas confirmadas
        df_p = pd.DataFrame(sh.worksheet("Proyectos").get_all_records())
        df_l = pd.DataFrame(sh.worksheet("Logistica").get_all_records())
        df_c = pd.DataFrame(sh.worksheet("Chat_Interno").get_all_records())
        
        # NORMALIZACIÓN: Columnas en minúsculas y sin espacios
        for df in [df_p, df_l, df_c]:
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
            
        return sh, df_p, df_l, df_c
    except Exception as e:
        st.error(f"⚠️ Error al leer el Excel: {e}")
        return None, None, None, None

sh, df_p, df_l, df_c = cargar_datos()

# --- NAVEGACIÓN ---
st.sidebar.title("🏗️ Grupo Magallan")
menu = st.sidebar.radio("Menú", ["📈 Tablero", "🏗️ Gestión de Obras", "🚚 Logística y Chat"])

if df_p is not None:
    # --- SECCIÓN TABLERO ---
    if menu == "📈 Tablero":
        st.header("📈 Tablero de Control")
        if not df_p.empty:
            hoy = datetime.now().date()
            # Conversión segura para cálculos
            df_p['fecha_entrega_dt'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
            
            # Alerta de atrasos
            atrasados = df_p[(df_p['fecha_entrega_dt'] < hoy) & (df_p['estado_fabricacion'] != "Entregado")]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Obras Totales", len(df_p))
            c2.metric("Atrasadas ⚠️", len(atrasados), delta=len(atrasados), delta_color="inverse")
            
            # Dinero (ajusta nombres si en tu excel son distintos)
            total = pd.to_numeric(df_p['monto_total_ars'], errors='coerce').sum()
            pagado = pd.to_numeric(df_p['pagado_ars'], errors='coerce').sum()
            c3.metric("Saldo por Cobrar", f"$ {total - pagado:,.2f}")

    # --- SECCIÓN GESTIÓN (NUEVO/EDITAR) ---
    elif menu == "🏗️ Gestión de Obras":
        tab1, tab2 = st.tabs(["🆕 Cargar Nuevo", "✏️ Editar Existente"])
        
        with tab1:
            with st.form("nuevo_p"):
                c1, c2 = st.columns(2)
                n_ppto = c1.number_input("Nro Presupuesto", step=1)
                n_cli = c1.text_input("Cliente")
                n_tot = c2.number_input("Monto Total")
                n_ent = c2.date_input("Fecha Entrega")
                if st.form_submit_button("Guardar"):
                    # El orden debe coincidir con tus columnas A, B, C...
                    sh.worksheet("Proyectos").append_row([n_ppto, n_cli, "Esperando", str(datetime.now().date()), str(n_ent), n_tot, 0, "Sin IVA", ""])
                    sh.worksheet("Logistica").append_row([n_ppto, "", str(n_ent), "Pendiente", ""])
                    st.success("Guardado.")
                    st.rerun()

    # --- SECCIÓN LOGÍSTICA Y CHAT (Solución KeyError nro_ppto) ---
    elif menu == "🚚 Logística y Chat":
        sel_ppto = st.sidebar.selectbox("Seleccione Obra:", df_p['nro_ppto'].unique())
        t1, t2 = st.tabs(["📦 Logística", "💬 Chat Interno"])
        
        with t1:
            idx_l = df_l[df_l['nro_ppto'].astype(str) == str(sel_ppto)].index
            if not idx_l.empty:
                dat_l = df_l.iloc[idx_l[0]]
                with st.form("edit_l"):
                    tecs = st.text_input("Técnicos", value=dat_l.get('tecnicos', ''))
                    if st.form_submit_button("Actualizar Técnicos"):
                        sh.worksheet("Logistica").update_cell(int(idx_l[0])+2, 2, tecs)
                        st.success("Actualizado.")

        with t2:
            st.subheader(f"Chat de Obra #{sel_ppto}")
            # Filtro seguro usando la columna normalizada
            mensajes = df_c[df_c['nro_ppto'].astype(str) == str(sel_ppto)]
            for _, m in mensajes.iterrows():
                with st.chat_message("user"):
                    st.write(f"*{m.get('usuario', 'NN')}*: {m.get('mensaje', '')}")
            
            with st.form("chat_f", clear_on_submit=True):
                msg = st.text_area("Mensaje")
                if st.form_submit_button("Enviar"):
                    sh.worksheet("Chat_Interno").append_row([sel_ppto, "Admin", datetime.now().strftime("%H:%M"), msg])
                    st.rerun()