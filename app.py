import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Configuración de la página
st.set_page_config(page_title="Grupo Magallan | Gestión", layout="wide", page_icon="🏗️")

# 2. Título principal
st.title("🏗️ Panel de Gestión Grupo Magallan")
st.markdown("---")

# 3. Función para limpiar y validar datos
def validar_datos(df):
    if df is not None and not df.empty:
        # Eliminamos filas que estén totalmente vacías
        df = df.dropna(how='all')
        return df
    return pd.DataFrame()

# 4. Conexión y Carga
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Intentamos cargar ambas pestañas
    df_proyectos = conn.read(worksheet="Proyectos", ttl=0)
    df_chat = conn.read(worksheet="Chat_Interno", ttl=0)
    
    # Validamos
    df_proyectos = validar_datos(df_proyectos)
    df_chat = validar_datos(df_chat)

    if not df_proyectos.empty:
        st.success("✅ Conexión establecida con éxito")
        
        # --- SIDEBAR: Selección de Presupuesto ---
        st.sidebar.header("Menú de Selección")
        lista_ppto = df_proyectos["nro_ppto"].unique()
        ppto_sel = st.sidebar.selectbox("Seleccione Nro de Presupuesto:", lista_ppto)
        
        # Filtrar datos del seleccionado
        datos_ppto = df_proyectos[df_proyectos["nro_ppto"] == ppto_sel].iloc[0]

        # --- CUERPO DEL PANEL ---
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Presupuesto", ppto_sel)
        with col2:
            st.metric("Cliente", datos_ppto['cliente'])
        with col3:
            estado = datos_ppto['estado_fabricacion']
            st.info(f"Estado: *{estado}*")

        st.markdown("---")

        # Pestañas para organizar la info
        tab1, tab2 = st.tabs(["📊 Detalles y Saldos", "💬 Chat Interno"])

        with tab1:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Datos de Fabricación")
                st.write(f"*Notas:* {datos_ppto['notas_planta']}")
            with c2:
                st.subheader("Control Financiero")
                total = float(datos_ppto['monto_total_ars'])
                pagado = float(datos_ppto['pagado_ars'])
                saldo = total - pagado
                st.write(f"*Monto Total:* $ {total:,.2f}")
                st.write(f"*Pagado:* $ {pagado:,.2f}")
                st.warning(f"*Saldo Pendiente: $ {saldo:,.2f}*")

        with tab2:
            st.subheader("Historial del Chat")
            mensajes = df_chat[df_chat["nro_ppto"] == ppto_sel]
            if not mensajes.empty:
                for _, m in mensajes.iterrows():
                    with st.chat_message(str(m['usuario']).lower()):
                        st.write(f"*{m['usuario']}* [{m['fecha_hora']}]: {m['mensaje']}")
            else:
                st.write("No hay mensajes registrados para este proyecto.")

    else:
        st.warning("⚠️ El archivo está conectado pero la pestaña 'Proyectos' no tiene datos.")
        st.info("Asegúrate de que la primera fila del Excel tenga los nombres de las columnas.")

except Exception as e:
    st.error("❌ Error crítico en la aplicación")
    st.write(f"Detalle del error: {e}")
    st.info("Revisa que el nombre de las pestañas en el Excel sean exactamente 'Proyectos' y 'Chat_Interno'.")