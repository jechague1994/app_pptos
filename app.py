import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Grupo Magallan", layout="wide")

st.title("🏗️ Panel de Gestión Grupo Magallan")

try:
    # Conexión directa usando los Secrets configurados
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Intentamos leer la pestaña Proyectos
    df_proyectos = conn.read(worksheet="Proyectos", ttl=0)
    
    if df_proyectos.empty:
        st.warning("El archivo está conectado pero la pestaña 'Proyectos' está vacía.")
    else:
        st.success("✅ ¡Datos cargados correctamente!")
        st.dataframe(df_proyectos)

except Exception as e:
    st.error(f"Error al leer los datos: {e}")