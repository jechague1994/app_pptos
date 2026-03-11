import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Grupo Magallan", layout="wide")

# Usamos SOLO el ID que confirmó el error 404
SPREADSHEET_ID = "1Bf2R7v_f-2_uV2M7uXq7y65oE9e_qV2M7uXq7y65oE9"

st.title("🏗️ Panel de Gestión Grupo Magallan")

try:
    # Conexión directa
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Le indicamos explícitamente el ID y la pestaña
    df_proyectos = conn.read(
        spreadsheet=SPREADSHEET_ID, 
        worksheet="Proyectos", 
        ttl=0
    )
    
    st.success("✅ ¡Conexión exitosa!")
    st.subheader("Listado de Proyectos")
    st.dataframe(df_proyectos)

except Exception as e:
    st.error("❌ Error de acceso.")
    st.warning(f"Detalle: {e}")
    st.info("Si el error persiste, verifica que el archivo no esté en la Papelera de Google Drive.")