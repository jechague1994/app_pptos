import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Magallan Dashboard Pro", layout="wide")

# Estilos CSS Estables
st.markdown("""
<style>
    [data-testid="stMetric"] { background: white; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; }
    .card-vendedor { background: white; border-radius: 8px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .card-corp { background: #f1f5f9; border-radius: 8px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #1e293b; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
@st.cache_resource(ttl=30) # Bajamos el cache para ver cambios rápido
def conectar_gs():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error de Credenciales: {e}")
        return None

def cargar_datos():
    gc = conectar_gs()
    if not gc: return pd.DataFrame(), None
    try:
        sh = gc.open("Gestion_Magallan")
        ws = sh.worksheet("Saldos_Simples")
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame(), ws
            
        df = pd.DataFrame(data)
        
        # Mapeo flexible de columnas por si cambiaste algún nombre
        rename_dict = {
            'Monto': 'Monto_Total', 'Total': 'Monto_Total',
            'Pago': 'Anticipo', 'Seña': 'Anticipo',
            'Fecha': 'Fecha_Aprobacion', 'Aprobado': 'Fecha_Aprobacion'
        }
        df = df.rename(columns=rename_dict)

        # Asegurar columnas mínimas para que no explote
        cols_necesarias = ['Monto_Total', 'Anticipo', 'Vendedor', 'Facturado', 'Cliente']
        for col in cols_necesarias:
            if col not in df.columns:
                st.error(f"⚠️ Falta la columna '{col}' en tu Excel.")
                return pd.DataFrame(), ws

        # Procesamiento numérico
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        
        # Procesamiento de fechas
        df['Fecha_Aprobacion'] = pd.to_datetime(df['Fecha_Aprobacion'], errors='coerce')
        df['Fecha_Creacion'] = pd.to_datetime(df.get('Fecha_Creacion', datetime.now()), errors='coerce')
        
        return df, ws
    except Exception as e:
        st.error(f"Error al leer la hoja: {e}")
        return pd.DataFrame(), None

# --- 3. DASHBOARD ---
df, ws = cargar_datos()

def fmt(n): return f"$ {n:,.0f}".replace(",", ".")

if not df.empty:
    st.title("📊 Magallan Dashboard")

    # --- MÉTRICAS ---
    m1, m2, m3 = st.columns(3)
    m1.metric("VENTAS TOTALES", fmt(df['Monto_Total'].sum()))
    m2.metric("TOTAL COBRADO", fmt(df['Anticipo'].sum()))
    m3.metric("SALDO PENDIENTE", fmt(df['Saldo'].sum()))

    st.divider()

    # --- GRÁFICOS ---
    g1, g2 = st.columns(2)
    with g1:
        st.plotly_chart(px.pie(df, values='Monto_Total', names='Vendedor', title="Ventas por Vendedor"), use_container_width=True)
    with g2:
        st.plotly_chart(px.bar(df.groupby('Facturado')['Monto_Total'].sum().reset_index(), x='Facturado', y='Monto_Total', title="Estado Facturación"), use_container_width=True)

    st.divider()

    # --- LISTADO Y CARGA ---
    col_list, col_form = st.columns([1.5, 1])

    with col_list:
        st.subheader("📑 Registros")
        st.dataframe(df[['Fecha_Creacion', 'Cliente', 'Vendedor', 'Monto_Total', 'Saldo']].sort_values(by='Fecha_Creacion', ascending=False))

    with col_form:
        st.subheader("📝 Nueva Entrada")
        with st.form("registro"):
            f_ppto = st.text_input("Nro Ppto")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto"])
            f_fac = st.selectbox("Factura", ["Facturado", "No Facturado"])
            f_tot = st.number_input("Total", min_value=0)
            f_ant = st.number_input("Anticipo", min_value=0)
            
            if st.form_submit_button("Guardar"):
                f_crea = datetime.now().strftime("%Y-%m-%d")
                # El orden debe ser: Fecha_Crea, Nro_Ppto, Cliente, Monto, Anticipo, Vendedor, Factura, Fecha_Apro, Corp
                ws.append_row([f_crea, f_ppto, f_cli, f_tot, f_ant, f_ven, f_fac, f_crea, "NO"])
                st.success("Guardado correctamente!")
                st.rerun()
else:
    st.warning("⚠️ No se detectaron datos. Revisa que tu Excel tenga los encabezados correctos.")