import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth

# Configuración de página
st.set_page_config(page_title="Sistema Magallan", layout="wide")

# Función de conexión robusta
@st.cache_resource(ttl=60)
def conectar_gs():
    try:
        # Extraemos la info de secretos
        info = dict(st.secrets["gcp_service_account"])
        # Limpieza de seguridad: reemplazamos los saltos de línea literales
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        
        creds = Credentials.from_service_account_info(
            info, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error de credenciales Google: {e}")
        return None

def obtener_datos():
    gc = conectar_gs()
    if not gc: return pd.DataFrame(), None
    try:
        sh = gc.open("Gestion_Magallan")
        ws = sh.worksheet("Saldos_Simples")
        df = pd.DataFrame(ws.get_all_records())
        
        # Limpieza de datos
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        return df, ws
    except Exception as e:
        st.error(f"Error al leer la planilla: {e}")
        return pd.DataFrame(), None

# --- RENDERIZADO ---
df, ws = obtener_datos()

if not df.empty:
    st.title("📊 Panel Magallan")
    
    # Métricas rápidas
    c1, c2, c3 = st.columns(3)
    c1.metric("Ventas Totales", f"${df['Monto_Total'].sum():,.0f}")
    c2.metric("Total Cobrado", f"${df['Anticipo'].sum():,.0f}")
    c3.metric("Pendiente", f"${df['Saldo'].sum():,.0f}")
    
    st.divider()
    
    # Mostrar tabla y buscador
    busqueda = st.text_input("Buscar cliente...")
    if busqueda:
        df = df[df.apply(lambda row: busqueda.lower() in str(row.values).lower(), axis=1)]
    
    st.dataframe(df, use_container_width=True)

else:
    st.info("Configurando conexión... Si el error persiste, verifica que el Excel esté compartido con el email del Service Account.")