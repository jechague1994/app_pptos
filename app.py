import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Magallan Dashboard", layout="wide")

# --- 2. CONEXIÓN (Simple y directa) ---
@st.cache_resource(ttl=60)
def conectar_gs():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def cargar_datos():
    gc = conectar_gs()
    if not gc: return pd.DataFrame(), None
    try:
        sh = gc.open("Gestion_Magallan")
        ws = sh.worksheet("Saldos_Simples")
        df = pd.DataFrame(ws.get_all_records())
        # Limpieza básica
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        return df, ws
    except:
        return pd.DataFrame(), None

# --- 3. DASHBOARD ---
df, ws = cargar_datos()

if not df.empty:
    st.title("📊 Magallan Intelligence")

    # MÉTRICAS
    m1, m2, m3 = st.columns(3)
    m1.metric("VENTAS TOTALES", f"$ {df['Monto_Total'].sum():,.0f}")
    m2.metric("COBRADO", f"$ {df['Anticipo'].sum():,.0f}")
    m3.metric("SALDO PENDIENTE", f"$ {df['Saldo'].sum():,.0f}")

    st.divider()

    # GRÁFICOS (Los 3 que te gustaban)
    g1, g2, g3 = st.columns(3)
    
    with g1:
        # Torta por Vendedor
        fig1 = px.pie(df, values='Monto_Total', names='Vendedor', title="Ventas por Vendedor")
        st.plotly_chart(fig1, use_container_width=True)
        
    with g2:
        # Barras Facturación
        fig2 = px.bar(df.groupby('Facturado')['Monto_Total'].sum().reset_index(), 
                      x='Facturado', y='Monto_Total', title="Estado de Factura")
        st.plotly_chart(fig2, use_container_width=True)
        
    with g3:
        # Histórico (Usa el índice como tiempo si la fecha falla)
        fig3 = px.line(df, y='Monto_Total', title="Tendencia de Ventas")
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # LISTADO Y FORMULARIO
    col_l, col_r = st.columns([1.5, 1])

    with col_l:
        st.subheader("📑 Pedidos Actuales")
        st.dataframe(df[['Cliente', 'Vendedor', 'Monto_Total', 'Saldo', 'Facturado']])
        
    with col_r:
        st.subheader("📝 Registrar Nueva Venta")
        with st.form("alta", clear_on_submit=True):
            f_ppto = st.text_input("Nro Presupuesto")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto"])
            f_fac = st.selectbox("Estado Factura", ["Facturado", "No Facturado"])
            f_tot = st.number_input("Monto Total", min_value=0)
            f_ant = st.number_input("Anticipo", min_value=0)
            
            if st.form_submit_button("Guardar"):
                hoy = datetime.now().strftime("%Y-%m-%d")
                ws.append_row([hoy, f_ppto, f_cli, f_tot, f_ant, f_ven, f_fac])
                st.success("¡Guardado!")
                st.rerun()
else:
    st.info("Conectado. Esperando datos del Excel...")