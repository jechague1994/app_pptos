import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Grupo Magallan", layout="wide")

# ID directo de tu archivo
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1Bf2R7v_f-2_uV2M7uXq7y65oE9e_qV2M7uXq7y65oE9/edit"

st.title("🏗️ Panel de Gestión Grupo Magallan")

try:
    # Intentamos la conexión
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Intentamos leer la pestaña 'Proyectos'
    # Si esto falla, el error aparecerá en pantalla
    df_proyectos = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Proyectos", ttl=0)
    
    st.success("✅ ¡Conexión exitosa! Leyendo datos...")
    st.dataframe(df_proyectos.head()) # Esto mostrará los primeros datos si funciona

except Exception as e:
    st.error("❌ No se pudo conectar con el Excel.")
    st.warning(f"Detalle técnico: {e}")
    st.info(f"Asegúrate de que este correo sea EDITOR: streamlit-magallan@app-magallan.iam.gserviceaccount.com")