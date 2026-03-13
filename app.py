import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Magallan Sistema Integrado", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .card-vendedor { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .card-corp { background: #f1f5f9; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #1e293b; border: 1px solid #cbd5e1; }
    .monto-alerta { color: #e11d48; font-weight: 800; font-size: 1.1rem; }
    .stMetric { background: white; padding: 10px; border-radius: 10px; border: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIONES ---
@st.cache_resource(ttl=60)
def conectar_gs():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error Google: {e}")
        return None

def cargar_datos():
    gc = conectar_gs()
    if not gc: return pd.DataFrame(), None
    try:
        sh = gc.open("Gestion_Magallan")
        ws = sh.worksheet("Saldos_Simples")
        df = pd.DataFrame(ws.get_all_records())
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        return df, ws
    except Exception as e:
        st.error(f"Error Datos: {e}")
        return pd.DataFrame(), None

# --- 3. INTERFAZ ---
df, ws = cargar_datos()

# PESTAÑAS
tab_dash, tab_pedidos, tab_jira = st.tabs(["📊 Dashboard de Ventas", "📝 Pedidos y Cobros", "🛠 Producción (Jira)"])

with tab_dash:
    if not df.empty:
        st.subheader("Estado General del Negocio")
        
        # Métricas principales
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("VENTAS TOTALES", f"${df['Monto_Total'].sum():,.0f}")
        m2.metric("COBRADO", f"${df['Anticipo'].sum():,.0f}")
        m3.metric("SALDO PENDIENTE", f"${df['Saldo'].sum():,.0f}")
        m4.metric("PEDIDOS ACTIVOS", len(df[df['Saldo'] > 0]))

        st.divider()
        
        # Gráficos Pro
        g1, g2, g3 = st.columns(3)
        
        with g1:
            # Ventas por Vendedor (Torta)
            fig_pie = px.pie(df, values='Monto_Total', names='Vendedor', title="Cuota por Vendedor", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with g2:
            # Evolución Mensual (Líneas)
            df_mes = df.dropna(subset=['Fecha']).copy()
            df_mes['Mes'] = df_mes['Fecha'].dt.strftime('%m-%Y')
            df_mes = df_mes.groupby('Mes')['Monto_Total'].sum().reset_index()
            fig_line = px.line(df_mes, x='Mes', y='Monto_Total', title="Evolución de Ventas", markers=True)
            st.plotly_chart(fig_line, use_container_width=True)
            
        with g3:
            # Estado de Facturación (Barras)
            fig_bar = px.bar(df.groupby('Facturado')['Monto_Total'].sum().reset_index(), 
                             x='Facturado', y='Monto_Total', color='Facturado', title="Monto por Facturación")
            st.plotly_chart(fig_bar, use_container_width=True)

with tab_pedidos:
    col_l, col_r = st.columns([1.8, 1.2])
    
    with col_l:
        st.subheader("📑 Cartera de Clientes")
        busc = st.text_input("🔍 Buscar cliente o vendedor...")
        df_f = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        for i, r in df_f.sort_values(by='Fecha', ascending=False).iterrows():
            clase = "card-corp" if str(r.get('Corporativa','')).upper() == "SI" else "card-vendedor"
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <b>{r['Cliente']}</b><br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']} | {r['Facturado']}</small>
                        </div>
                        <div style="text-align:right;">
                            <small>SALDO</small><br>
                            <span class="monto-alerta">${r['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar Cobro"):
                nv = st.number_input("Total cobrado", value=float(r['Anticipo']), key=f"upd_{i}")
                if st.button("Guardar", key=f"btn_{i}"):
                    ws.update_cell(i+2, 5, nv)
                    st.rerun()

    with col_r:
        st.subheader("📝 Nueva Venta")
        with st.form("alta", clear_on_submit=True):
            f_ppto = st.text_input("Nro Presupuesto")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            f_fac = st.selectbox("Factura", ["Facturado", "Sin Facturar", "Pendiente"])
            f_tot = st.number_input("Total $", min_value=0.0)
            f_ant = st.number_input("Anticipo $", min_value=0.0)
            f_corp = st.checkbox("Cuenta Corporativa")
            if st.form_submit_button("REGISTRAR"):
                hoy = datetime.now().strftime("%Y-%m-%d")
                ws.append_row([hoy, f_ppto, f_cli, f_tot, f_ant, f_ven, f_fac, hoy, "SI" if f_corp else "NO"])
                st.success("¡Venta guardada!")
                st.rerun()

with tab_jira:
    st.subheader("⚙️ Tablero de Producción")
    # Sacamos la URL de tus secretos. 
    # Asegúrate de que en Secrets sea la URL del TABLERO (ej: https://magallan.atlassian.net/jira/software/projects/PROJ/boards/1)
    jira_url = st.secrets["jira"]["url"]
    
    st.markdown(f'<iframe src="{jira_url}" width="100%" height="800" style="border:none;"></iframe>', unsafe_allow_html=True