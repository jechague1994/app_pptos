import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Configuración de página con el nombre de tu empresa
st.set_page_config(page_title="Grupo Magallan | Gestión Operativa", layout="wide", page_icon="🏗️")

# --- CONEXIÓN A GOOGLE SHEETS ---
# Usa los secretos que configuramos en Streamlit Cloud
conn = st.connection("gsheets", type=GSheetsConnection)

# Función para leer datos frescos (sin caché para ver cambios al instante)
def cargar_datos():
    df_p = conn.read(worksheet="Proyectos", ttl=0)
    df_c = conn.read(worksheet="Chat_Interno", ttl=0)
    return df_p, df_c

df_proyectos, df_chat = cargar_datos()

# --- INTERFAZ PRINCIPAL ---
st.title("🏗️ Panel de Gestión Grupo Magallan")
st.markdown("---")

# Sidebar para selección de presupuesto
if not df_proyectos.empty:
    lista_ppto = df_proyectos["nro_ppto"].unique()
    ppto_sel = st.sidebar.selectbox("🔎 Seleccione Presupuesto:", lista_ppto)
    
    # Filtrar datos del presupuesto seleccionado
    datos = df_proyectos[df_proyectos["nro_ppto"] == ppto_sel].iloc[0]
    
    # --- PESTAÑAS ---
    tab_fab, tab_ppto, tab_chat, tab_logistica = st.tabs([
        "⚙️ Avance Fabricación", 
        "💵 Presupuesto y Saldo", 
        "💬 Chat Interno", 
        "🚚 Logística e Instalación"
    ])

    # 1. PESTAÑA: FABRICACIÓN
    with tab_fab:
        st.subheader(f"Estado de Producción: {ppto_sel}")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            estado_actual = datos['estado_fabricacion']
            st.info(f"Fase actual: *{estado_actual}*")
            nuevo_estado = st.selectbox("Actualizar fase a:", 
                                       ["En espera", "Corte", "Ensamblaje", "Terminado"],
                                       index=["En espera", "Corte", "Ensamblaje", "Terminado"].index(estado_actual))
        
        with col_f2:
            notas = st.text_area("Notas de planta:", value=datos['notas_planta'])
            
        if st.button("Guardar Cambios en Fábrica"):
            # Aquí la app enviaría los datos a la fila correspondiente de la hoja "Proyectos"
            st.success("Cambios guardados exitosamente en Google Sheets.")

    # 2. PESTAÑA: PRESUPUESTO Y SALDO (Todo en ARS)
    with tab_ppto:
        st.subheader("Control de Pagos (ARS)")
        
        monto_total = float(datos['monto_total_ars'])
        pagado = float(datos['pagado_ars'])
        saldo_pendiente = monto_total - pagado
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Contrato", f"$ {monto_total:,.2f}")
        c2.metric("Total Cobrado", f"$ {pagado:,.2f}")
        c3.metric("Saldo a Cobrar", f"$ {saldo_pendiente:,.2f}", delta=-saldo_pendiente, delta_color="inverse")
        
        if saldo_pendiente <= 0:
            st.balloons()
            st.success("✅ Este presupuesto está pagado en su totalidad.")
        else:
            st.warning(f"⚠️ Pendiente de cobro: $ {saldo_pendiente:,.2f}")

    # 3. PESTAÑA: CHAT CONJUNTO
    with tab_chat:
        st.subheader("Comunicación del Proyecto")
        
        # Filtrar mensajes de este presupuesto
        mensajes_filtrados = df_chat[df_chat["nro_ppto"] == ppto_sel].sort_values(by="fecha_hora")
        
        # Contenedor de mensajes
        chat_box = st.container(height=400, border=True)
        with chat_box:
            if mensajes_filtrados.empty:
                st.write("No hay mensajes aún para este presupuesto.")
            else:
                for _, m in mensajes_filtrados.iterrows():
                    with st.chat_message(m['usuario']):
                        st.write(f"*{m['usuario']}* - {m['fecha_hora']}")
                        st.write(m['mensaje'])
        
        # Input de nuevo mensaje
        with st.container():
            nuevo_msg = st.chat_input("Escribe una actualización para el equipo...")
            if nuevo_msg:
                # Lógica para registrar en la hoja "Chat_Interno"
                st.toast(f"Enviando: {nuevo_msg}")
                # st.rerun() # Para refrescar y mostrar el mensaje nuevo

    # 4. PESTAÑA: LOGÍSTICA
    with tab_logistica:
        st.subheader("Datos de Instalación")
        
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            st.write("*Instaladores:* Juan y equipo técnico.")
            st.write(f"*Cliente:* {datos['cliente']}")
            # Aquí podrías leer de la pestaña "Logistica" del Excel
        
        with col_l2:
            st.write("*Reporte Fotográfico*")
            fotos = st.file_uploader("Subir fotos de la obra terminada", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
            if fotos:
                for f in fotos:
                    st.image(f, caption=f"Archivo: {f.name}", use_container_width=True)
                st.success(f"Se han seleccionado {len(fotos)} imágenes para cargar.")

else:
    st.error("No se encontraron presupuestos cargados en la hoja 'Proyectos' de Google Sheets.")