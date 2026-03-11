import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Grupo Magallan", layout="wide")
st.title("🏗️ Panel de Gestión Grupo Magallan")

# Intentamos la conexión
conn = st.connection("gsheets", type=GSheetsConnection)

# Intentamos leer la pestaña
try:
    # Si pusiste el ID en los Secrets, esto lo usará automáticamente
    df = conn.read(worksheet="Proyectos", ttl=0)
    
    if df is not None and not df.empty:
        st.success("✅ ¡Datos cargados!")
        st.write("Visualización de la tabla:")
        st.dataframe(df)
    else:
        st.warning("⚠️ El archivo está conectado, pero la pestaña 'Proyectos' parece no tener datos o encabezados.")
        st.info("Asegúrate de que la primera fila tenga los nombres de las columnas.")

except Exception as e:
    st.error(f"Error al interpretar los datos: {e}")