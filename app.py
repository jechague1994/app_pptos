import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
import re  # IMPORTACIÓN CRÍTICA PARA JIRA

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Magallan Dashboard Pro", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .card-vendedor { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .card-corp { background: #f1f5f9; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #1e293b; border: 1px solid #cbd5e1; }
    .status-badge { background: #0052CC; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.8rem; font-weight: bold; }
    .monto-alerta { color: #e11d48; font-weight: 800; font-size: 1.1rem; }
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
        # Match limpio para Jira
        df['Nro_Ppto_Match'] = df['Nro_Ppto'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        return df, ws
    except: return pd.DataFrame(), None

def consultar_jira_api():
    try:
        conf = st.secrets["jira"]
        url = f"{conf['url'].strip().rstrip('/')}/rest/api/3/search"
        auth = HTTPBasicAuth(conf["user"], conf["token"].strip())
        params = {'jql': f'project="{conf["project_key"].strip()}"', 'fields': 'summary,status', 'maxResults': 100}
        res = requests.get(url, params=params, auth=auth, timeout=10)
        if res.status_code == 200:
            issues = res.json().get('issues', [])
            mapa = {}
            for iss in issues:
                summary = str(iss['fields'].get('summary', ''))
                status = iss['fields']['status']['name']
                # Busca números de presupuesto en el título (ej: 12423)
                nums = re.findall(r'\d+', summary)
                for n in nums: mapa[n] = status
            return mapa
    except: return {}

# --- 3. LÓGICA DE NEGOCIO ---
df, ws = cargar_datos()
dict_jira = consultar_jira_api()

if not df.empty:
    st.title("📊 Magallan Intelligence")

    # --- SECCIÓN 1: MÉTRICAS Y GRÁFICOS (ARRIBA) ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS TOTALES", f"${df['Monto_Total'].sum():,.0f}")
    m2.metric("COBRADO", f"${df['Anticipo'].sum():,.0f}")
    m3.metric("SALDO PENDIENTE", f"${df['Saldo'].sum():,.0f}")
    m4.metric("TICKETS JIRA", len(dict_jira))

    st.subheader("Análisis de Rendimiento")
    g1, g2, g3 = st.columns(3)
    
    with g1:
        # Gráfico de Torta: Ventas por Vendedor
        fig_v = px.pie(df, values='Monto_Total', names='Vendedor', title="Ventas por Vendedor", hole=0.4)
        st.plotly_chart(fig_v, use_container_width=True)
    
    with g2:
        # Gráfico de Barras: Facturación (CORREGIDO: Facturado / Sin Factura)
        df_fac = df.groupby('Facturado')['Monto_Total'].sum().reset_index()
        fig_f = px.bar(df_fac, x='Facturado', y='Monto_Total', color='Facturado', title="Monto por Facturación")
        st.plotly_chart(fig_f, use_container_width=True)
    
    with g3:
        # Línea de tiempo de ventas
        df_mes = df.dropna(subset=['Fecha']).copy()
        df_mes['Mes'] = df_mes['Fecha'].dt.strftime('%b %y')
        df_line = df_mes.groupby('Mes')['Monto_Total'].sum().reset_index()
        fig_t = px.line(df_line, x='Mes', y='Monto_Total', title="Evolución de Ventas", markers=True)
        st.plotly_chart(fig_t, use_container_width=True)

    st.divider()

    # --- SECCIÓN 2: LISTADO Y REGISTRO (ABAJO) ---
    col_l, col_r = st.columns([1.8, 1.2])

    with col_l:
        st.subheader("📑 Gestión de Cartera")
        busc = st.text_input("🔍 Buscar por cliente o ppto...")
        df_f = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        for i, r in df_f.sort_values(by='Fecha', ascending=False).iterrows():
            est_jira = dict_jira.get(r['Nro_Ppto_Match'], "Sin Ticket")
            clase = "card-corp" if str(r.get('Corporativa','')).upper() == "SI" else "card-vendedor"
            
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <b>{r['Cliente']}</b> <span class="status-badge">{est_jira}</span><br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']} | {r['Facturado']}</small>
                        </div>
                        <div style="text-align:right;">
                            <span class="monto-alerta">${r['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar Pago"):
                nv = st.number_input("Total cobrado", value=float(r['Anticipo']), key=f"u_{i}")
                if st.button("Guardar", key=f"b_{i}"):
                    ws.update_cell(i+2, 5, nv)
                    st.rerun()

    with col_r:
        st.subheader("📝 Nueva Venta")
        with st.form("alta", clear_on_submit=True):
            f_ppto = st.text_input("Nro Presupuesto")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            # OPCIONES CORREGIDAS SEGÚN TU PEDIDO
            f_fac = st.selectbox("Estado Factura", ["Facturado", "Sin Factura"])
            f_tot = st.number_input("Monto Total", min_value=0.0)
            f_ant = st.number_input("Anticipo", min_value=0.0)
            f_corp = st.checkbox("Cuenta Corporativa")
            if st.form_submit_button("REGISTRAR"):
                hoy = datetime.now().strftime("%Y-%m-%d")
                ws.append_row([hoy, f_ppto, f_cli, f_tot, f_ant, f_ven, f_fac, hoy, "SI" if f_corp else "NO"])
                st.success("¡Venta cargada con éxito!"); st.rerun()
else:
    st.info("Conectado. Esperando datos del Excel...")