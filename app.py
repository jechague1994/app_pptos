import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Configuración de página
st.set_page_config(page_title="Grupo Magallan | Gestión Operativa", layout="wide", page_icon="🏗️")

# 2. El ID de tu Excel (Extraído de tu URL)
SPREADSHEET_ID = "1Bf2R7v_f-2_uV2M7uXq7y65oE9e_qV2M7uXq7y65oE9"

# 3. Conexión Estable
# Intentamos conectar usando la configuración de Secrets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Error en la conexión inicial. Revisa los Secrets en Streamlit Cloud.")
    st.stop()

# 4. Función de carga de datos optimizada
def cargar_todo():
    # Forzamos la lectura usando el ID directo para evitar el error SpreadsheetNotFound
    df_p = conn.read(spreadsheet=SPREADSHEET_ID, worksheet="Proyectos", ttl=0)
    df_c = conn.read(spreadsheet=SPREADSHEET_ID, worksheet="Chat_Interno", ttl=0)
    return df_p, df_c

# Ejecutar carga
try:
    df_proyectos, df_chat = cargar_todo()
except Exception as e:
    st.error(f"No se pudo leer el Excel. Verifica que el correo de la Cuenta de Servicio sea EDITOR en el archivo compartido.")
    st.info("Correo a compartir: streamlit-magallan@app-magallan.iam.gserviceaccount.com")
    st.stop()

# --- INTERFAZ DEL PANEL ---
st.title("🏗️ Panel de Gestión Grupo Magallan")
st.markdown("---")

if not df_proyectos.empty:
    # Sidebar: Selección de presupuesto
    lista_ppto = df_proyectos["nro_ppto"].unique()
    ppto_sel = st.sidebar.selectbox("🔎 Seleccione Presupuesto:", lista_ppto)
    
    # Datos del presupuesto seleccionado
    datos = df_proyectos[df_proyectos["nro_ppto"] == ppto_sel].iloc[0]
    
    # Pestañas de trabajo
    tab_fab, tab_ppto, tab_chat = st.tabs(["⚙️ Fabricación", "💵 Saldos (ARS)", "💬 Chat Interno"])

    with tab_fab:
        st.subheader(f"Estado: {ppto_sel}")
        c1, c2 = st.columns(2)
        with c1:
            st.info(f"Fase actual: *{datos['estado_fabricacion']}*")
        with c2:
            st.write(f"*Notas de Planta:* {datos['notas_planta']}")

    with tab_ppto:
        st.subheader("Control de Pagos")
        total = float(datos['monto_total_ars'])
        pagado = float(datos['pagado_ars'])
        saldo = total - pagado
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Presupuesto", f"$ {total:,.2f}")
        col2.metric("Ya Pagado", f"$ {pagado:,.2f}")
        col3.metric("Saldo Pendiente", f"$ {saldo:,.2f}", delta=-saldo, delta_color="inverse")

    with tab_chat:
        st.subheader("Historial de mensajes")
        # Filtrar chat
        mensajes = df_chat[df_chat["nro_ppto"] == ppto_sel]
        if mensajes.empty:
            st.write("Sin mensajes.")
        else:
            for _, m in mensajes.iterrows():
                with st.chat_message(m['usuario']):
                    st.write(f"*{m['usuario']}* ({m['fecha_hora']}): {m['mensaje']}")
else:
    st.warning("El archivo de Excel parece estar vacío.")