import streamlit as st
import pandas as pd

# Configuración de página
st.set_page_config(page_title="Grupo Magallan | Gestión", layout="wide")

st.title("🏗️ Panel de Gestión Operativa - Grupo Magallan")

# URL de tu Google Sheet (formato export para pandas)
SHEET_ID = "1Bf2R7v_f-2_uV2M7uXq7y65oE9e_qV2M7uXq7y65oE9"

@st.cache_data(ttl=60)
def cargar_pestaña(nombre_pestaña):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={nombre_pestaña}"
    return pd.read_csv(url)

try:
    # Cargamos las 3 pestañas de forma independiente
    df_proyectos = cargar_pestaña("Proyectos")
    df_logistica = cargar_pestaña("Logistica")
    df_chat = cargar_pestaña("Chat_Interno")

    # Limpiamos nombres de columnas (quitar espacios y minúsculas)
    df_proyectos.columns = [c.strip().lower() for c in df_proyectos.columns]
    df_logistica.columns = [c.strip().lower() for c in df_logistica.columns]
    df_chat.columns = [c.strip().lower() for c in df_chat.columns]

    # Sidebar: Selección de Obra
    st.sidebar.header("Selección de Obra")
    nro_col = "nro_ppto"
    lista_ppto = df_proyectos[nro_col].unique()
    ppto_sel = st.sidebar.selectbox("Seleccione Nro de Presupuesto:", lista_ppto)

    # Filtrado de datos por presupuesto
    datos_p = df_proyectos[df_proyectos[nro_col] == ppto_sel].iloc[0]
    
    # Interfaz de pestañas
    t1, t2, t3 = st.tabs(["📊 Fabricación", "🚚 Logística", "💬 Chat"])

    with t1:
        c1, c2 = st.columns(2)
        c1.metric("Cliente", datos_p.get('cliente', 'N/A'))
        c1.write(f"*Estado:* {datos_p.get('estado_fabricacion', '-')}")
        
        total = float(datos_p.get('monto_total_ars', 0))
        pagado = float(datos_p.get('pagado_ars', 0))
        c2.metric("Saldo Pendiente", f"$ {total - pagado:,.2f}")

    with t2:
        if ppto_sel in df_logistica[nro_col].values:
            datos_l = df_logistica[df_logistica[nro_col] == ppto_sel].iloc[0]
            st.write(f"*Técnicos:* {datos_l.get('tecnicos', 'No asignados')}")
            st.write(f"*Fecha Instalación:* {datos_l.get('fecha_instalacion', 'Pendiente')}")
            st.info(f"*Estado Entrega:* {datos_l.get('estado_entrega', '-')}")
        else:
            st.warning("No hay datos de logística para este presupuesto.")

    with t3:
        mensajes = df_chat[df_chat[nro_col].astype(str) == str(ppto_sel)]
        if not mensajes.empty:
            for _, m in mensajes.iterrows():
                with st.chat_message("user"):
                    st.write(f"*{m.get('usuario', 'Admin')}*: {m.get('mensaje', '')}")
        else:
            st.write("Sin mensajes.")

except Exception as e:
    st.error("Error al cargar datos. Verifica que el nombre de las pestañas sea exacto.")
    st.info("Pestañas requeridas: 'Proyectos', 'Logistica', 'Chat_Interno'")