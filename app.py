import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. CONFIGURACIÓN Y ESTILOS
st.set_page_config(page_title="Grupo Magallan | Gestión 360", layout="wide", page_icon="🏗️")

st.markdown("""
    <style>
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; }
    .alerta-roja { color: white; background-color: #ff4b4b; padding: 12px; border-radius: 8px; font-weight: bold; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# 2. CONEXIÓN SEGURA CON GOOGLE SHEETS
@st.cache_resource
def conectar_google():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"❌ Error de Secretos: {e}. Revisa el panel de Streamlit Cloud.")
        st.stop()

client = conectar_google()
SHEET_NAME = "Gestion_Magallan"

# 3. CARGA Y LIMPIEZA DE DATOS
def cargar_datos():
    try:
        sh = client.open(SHEET_NAME)
        # Cargamos las 3 pestañas confirmadas
        ws_p = sh.worksheet("Proyectos")
        ws_l = sh.worksheet("Logistica")
        ws_c = sh.worksheet("Chat_Interno")
        
        df_p = pd.DataFrame(ws_p.get_all_records())
        df_l = pd.DataFrame(ws_l.get_all_records())
        df_c = pd.DataFrame(ws_c.get_all_records())

        # Limpieza de nombres de columnas para evitar KeyErrors
        for df in [df_p, df_l, df_c]:
            df.columns = df.columns.str.strip()
            
        return sh, df_p, df_l, df_c
    except Exception as e:
        st.error(f"⚠️ Error al abrir pestañas: {e}. Verifica los nombres en el Excel.")
        return None, None, None, None

sh, df_p, df_l, df_c = cargar_datos()

# --- NAVEGACIÓN LATERAL ---
st.sidebar.title("🏗️ Grupo Magallan")
menu = st.sidebar.radio("Menú Principal", ["📈 Tablero de Control", "🏗️ Gestión de Obras", "🚚 Logística y Chat"])

if df_p is not None:
    # --- SECCIÓN 1: TABLERO DE CONTROL ---
    if menu == "📈 Tablero de Control":
        st.header("📈 Tablero de Control Inteligente")
        
        if not df_p.empty:
            hoy = datetime.now().date()
            # Conversión segura de fechas y números
            df_p['Fecha_Entrega_DT'] = pd.to_datetime(df_p['Fecha_Entrega'], errors='coerce').dt.date
            df_p['Monto_Total_Ars'] = pd.to_numeric(df_p['Monto_Total_Ars'], errors='coerce').fillna(0)
            df_p['Pagado_Ars'] = pd.to_numeric(df_p['Pagado_Ars'], errors='coerce').fillna(0)
            
            # Filtro de Atrasados
            atrasados = df_p[(df_p['Fecha_Entrega_DT'] < hoy) & (df_p['Estado_Fabricacion'] != "Entregado")]
            total_deuda = df_p['Monto_Total_Ars'].sum() - df_p['Pagado_Ars'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Obras en Sistema", len(df_p))
            c2.metric("Entregas Vencidas ⚠️", len(atrasados), delta=len(atrasados), delta_color="inverse")
            c3.metric("Saldo Pendiente Total", f"$ {total_deuda:,.2f}")

            st.divider()
            
            if not atrasados.empty:
                st.markdown('<p class="alerta-roja">🚨 OBRAS FUERA DE FECHA DE ENTREGA</p>', unsafe_allow_html=True)
                st.dataframe(atrasados[['Nro_Ppto', 'Cliente', 'Fecha_Entrega', 'Estado_Fabricacion']], use_container_width=True)
            else:
                st.success("✅ Todas las entregas están al día.")

    # --- SECCIÓN 2: GESTIÓN DE OBRAS ---
    elif menu == "🏗️ Gestión de Obras":
        tab1, tab2 = st.tabs(["🆕 Nueva Carga", "✏️ Editar Existente"])
        
        with tab1:
            st.subheader("Cargar Nuevo Presupuesto")
            with st.form("form_nuevo", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    n_ppto = st.number_input("Nro Presupuesto", step=1)
                    n_cliente = st.text_input("Nombre del Cliente")
                    n_iva = st.selectbox("Condición IVA", ["Sin IVA", "Con IVA (21%)"])
                with col2:
                    n_total = st.number_input("Monto Total (ARS)", min_value=0.0)
                    n_pago = st.number_input("Anticipo", min_value=0.0)
                    n_entrega = st.date_input("Fecha Prometida Entrega")
                
                if st.form_submit_button("Guardar Presupuesto"):
                    if n_ppto and n_cliente:
                        nueva_fila = [n_ppto, n_cliente, "Esperando", str(datetime.now().date()), str(n_entrega), n_total, n_pago, n_iva, ""]
                        sh.worksheet("Proyectos").append_row(nueva_fila)
                        # También creamos fila en Logística para sincronizar
                        sh.worksheet("Logistica").append_row([n_ppto, "", str(n_entrega), "Pendiente", "", ""])
                        st.success("✅ Presupuesto guardado y sincronizado con logística.")
                        st.rerun()

        with tab2:
            st.subheader("Editar Estado y Finanzas")
            ppto_sel = st.selectbox("Buscar Presupuesto:", df_p['Nro_Ppto'].unique())
            idx = df_p[df_p['Nro_Ppto'] == ppto_sel].index[0]
            datos = df_p.iloc[idx]
            
            with st.form("form_edit"):
                c1, c2 = st.columns(2)
                nuevo_est = c1.selectbox("Estado Fabricación", ["Esperando", "Preparacion", "Terminado", "Entregado"], 
                                       index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(datos['Estado_Fabricacion']) if datos['Estado_Fabricacion'] in ["Esperando", "Preparacion", "Terminado", "Entregado"] else 0)
                nuevo_pagado = c1.number_input("Actualizar Pagado", value=float(datos['Pagado_Ars']))
                nuevas_notas = c2.text_area("Notas Planta", value=datos.get('notas_planta', ''))
                
                if st.form_submit_button("Actualizar Datos"):
                    ws = sh.worksheet("Proyectos")
                    fila = int(idx) + 2
                    ws.update_cell(fila, 3, nuevo_est) # Columna C
                    ws.update_cell(fila, 6, nuevo_pagado) # Columna F
                    ws.update_cell(fila, 4, nuevas_notas) # Columna D
                    st.success("✅ Cambios aplicados.")
                    st.rerun()

    # --- SECCIÓN 3: LOGÍSTICA Y CHAT ---
    elif menu == "🚚 Logística y Chat":
        ppto_sel = st.sidebar.selectbox("Seleccione Obra:", df_p['Nro_Ppto'].unique())
        t_log, t_chat = st.tabs(["📦 Datos de Obra", "💬 Chat Interno"])
        
        with t_log:
            idx_l = df_l[df_l['Nro_Ppto'] == ppto_sel].index
            if not idx_l.empty:
                d_l = df_l.iloc[idx_l[0]]
                with st.form("log_edit"):
                    tecs = st.text_input("Técnicos Asignados", value=d_l['Tecnicos'])
                    f_fotos = st.text_input("URL Carpeta Fotos (Drive)", value=d_l['Url_Fotos'])
                    if st.form_submit_button("Guardar en Logística"):
                        ws_l = sh.worksheet("Logistica")
                        ws_l.update_cell(int(idx_l[0])+2, 2, tecs)
                        ws_l.update_cell(int(idx_l[0])+2, 5, f_fotos)
                        st.success("Logística actualizada.")
            else:
                st.warning("No se encontró este presupuesto en la pestaña Logística.")

        with t_chat:
            st.subheader(f"Comunicación Obra #{ppto_sel}")
            mensajes = df_c[df_c['nro_ppto'].astype(str) == str(ppto_sel)]
            for _, m in mensajes.iterrows():
                with st.chat_message("user"):
                    st.write(f"*{m['usuario']}* [{m['fecha_hora']}]: {m['mensaje']}")
            
            with st.form("msg_form", clear_on_submit=True):
                u_name = st.text_input("Nombre", value="Oficina")
                u_msg = st.text_area("Mensaje...")
                if st.form_submit_button("Enviar al Equipo"):
                    sh.worksheet("Chat_Interno").append_row([datetime.now().strftime("%d/%m %H:%M"), ppto_sel, u_name, u_msg])
                    st.rerun()