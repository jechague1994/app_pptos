import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Configuración de la página
st.set_page_config(page_title="Grupo Magallan | Gestión Total", layout="wide", page_icon="🏗️")

st.title("🏗️ Panel de Gestión Operativa - Grupo Magallan")
st.markdown("---")

# 2. Conexión centralizada
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Carga de las 3 pestañas
    df_proyectos = conn.read(worksheet="Proyectos", ttl=0)
    df_logistica = conn.read(worksheet="Logistica", ttl=0)
    df_chat = conn.read(worksheet="Chat_Interno", ttl=0)

    # Limpieza de columnas para evitar errores de tipeo
    for df in [df_proyectos, df_logistica, df_chat]:
        if df is not None:
            df.columns = [c.strip().lower() for c in df.columns]

    if not df_proyectos.empty:
        # Sidebar de navegación
        st.sidebar.header("Selección de Obra")
        # Usamos nro_ppto como ID principal
        lista_ppto = df_proyectos["nro_ppto"].unique()
        ppto_sel = st.sidebar.selectbox("Nro de Presupuesto:", lista_ppto)
        
        # Filtrado de datos
        datos_p = df_proyectos[df_proyectos["nro_ppto"] == ppto_sel].iloc[0]
        
        # 3. INTERFAZ POR PESTAÑAS
        tab1, tab2, tab3 = st.tabs(["📊 Fabricación y Saldos", "🚚 Logística e Instalación", "💬 Chat Interno"])

        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Estado de Obra")
                st.info(f"*Cliente:* {datos_p.get('cliente', 'N/A')}")
                st.write(f"*Estado:* {datos_p.get('estado_fabricacion', 'N/A')}")
                st.write(f"*Notas:* {datos_p.get('notas_planta', '-')}")
            
            with col2:
                st.subheader("Situación Financiera")
                total = float(datos_p.get('monto_total_ars', 0))
                pagado = float(datos_p.get('pagado_ars', 0))
                st.metric("Saldo Pendiente", f"$ {total - pagado:,.2f}", delta_color="inverse")
                st.write(f"Total: $ {total:,.2f} | Pagado: $ {pagado:,.2f}")

        with tab2:
            st.subheader("Seguimiento de Entrega")
            # Buscamos en la pestaña Logistica el mismo presupuesto
            if not df_logistica.empty and ppto_sel in df_logistica["nro_ppto"].values:
                datos_l = df_logistica[df_logistica["nro_ppto"] == ppto_sel].iloc[0]
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Técnicos Asignados", datos_l.get('tecnicos', 'Sin asignar'))
                c2.metric("Fecha Instalación", str(datos_l.get('fecha_instalacion', 'Pendiente')))
                c3.metric("Estado Entrega", datos_l.get('estado_entrega', 'Pendiente'))
                
                if 'url_fotos' in datos_l and pd.notna(datos_l['url_fotos']):
                    st.link_button("📂 Ver Fotos de Instalación", datos_l['url_fotos'])
            else:
                st.warning("No hay datos de logística cargados para este presupuesto.")

        with tab3:
            st.subheader("Historial de Coordinación")
            mensajes = df_chat[df_chat["nro_ppto"].astype(str) == str(ppto_sel)]
            if not mensajes.empty:
                for _, m in mensajes.iterrows():
                    with st.chat_message("user"):
                        st.write(f"*{m.get('usuario', 'Admin')}*: {m.get('mensaje', '')}")
                        st.caption(f"{m.get('fecha_hora', '')}")
            else:
                st.write("Sin mensajes.")

    else:
        st.error("No se encontraron datos en la pestaña 'Proyectos'.")

except Exception as e:
    st.error(f"Error de conexión: {e}")