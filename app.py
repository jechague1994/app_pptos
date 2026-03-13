import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
import re

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard Magallan Pro", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    .card-vendedor { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .card-corp { background: #f8fafc; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #1e293b; border: 1px solid #e2e8f0; }
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
        # Limpieza para el match
        df['Nro_Ppto_Match'] = df['Nro_Ppto'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        return df, ws
    except Exception as e:
        st.error(f"Error Excel: {e}")
        return pd.DataFrame(), None

def consultar_jira():
    try:
        conf = st.secrets["jira"]
        # Forzamos la URL de búsqueda v3
        url = f"{conf['url'].strip().rstrip('/')}/rest/api/3/search"
        auth = HTTPBasicAuth(conf["user"], conf["token"].strip())
        
        # JQL simplificado para asegurar respuesta
        params = {
            'jql': f'project="{conf["project_key"].strip()}"',
            'fields': 'summary,status', 
            'maxResults': 100
        }
        
        res = requests.get(url, params=params, auth=auth, timeout=15)
        if res.status_code == 200:
            data = res.json()
            mapa = {}
            for iss in data.get('issues', []):
                # Extraemos el título del ticket (Summary)
                summary = str(iss['fields'].get('summary', ''))
                status = iss['fields']['status']['name']
                # Buscamos números de 4 o 5 dígitos (presupuestos)
                nums = re.findall(r'\d{4,6}', summary)
                for n in nums:
                    mapa[n] = status
            return mapa
    except Exception as e:
        st.sidebar.warning(f"Jira Offline: {e}")
        return {}

# --- 3. LÓGICA Y DASHBOARD ---
df, ws = cargar_datos()
dict_jira = consultar_jira()

if not df.empty:
    st.title("📊 Magallan Intelligence")
    
    # MÉTRICAS RÁPIDAS
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS TOTALES", f"${df['Monto_Total'].sum():,.0f}")
    m2.metric("COBRADO", f"${df['Anticipo'].sum():,.0f}")
    m3.metric("DEUDA", f"${df['Saldo'].sum():,.0f}", delta_color="inverse")
    m4.metric("TICKETS ACTIVOS", len(dict_jira))

    # --- SECCIÓN DE GRÁFICOS (ARRIBA) ---
    g1, g2 = st.columns([1, 1])
    
    with g1:
        # Gráfico 1: Ventas por Vendedor (Torta Pro)
        fig_pie = px.pie(df, values='Monto_Total', names='Vendedor', 
                         title="Distribución de Ventas por Vendedor", 
                         hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_pie, use_container_width=True)

    with g2:
        # Gráfico 2: Evolución de Cobranza (Área)
        df_f = df.dropna(subset=['Fecha']).sort_values('Fecha')
        df_f['Mes'] = df_f['Fecha'].dt.strftime('%Y-%m')
        df_mes = df_f.groupby('Mes')[['Monto_Total', 'Anticipo']].sum().reset_index()
        fig_area = px.area(df_mes, x='Mes', y=['Monto_Total', 'Anticipo'], 
                           title="Ventas vs Cobranza en el Tiempo",
                           barmode='group')
        st.plotly_chart(fig_area, use_container_width=True)

    st.divider()

    # --- SECCIÓN OPERATIVA (ABAJO) ---
    col_list, col_form = st.columns([1.8, 1.2])

    with col_list:
        st.subheader("📑 Cartera de Pedidos")
        busc = st.text_input("🔍 Buscar cliente o ppto...")
        df_view = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        for i, r in df_view.sort_values(by='Fecha', ascending=False).iterrows():
            # Buscamos en el diccionario de Jira
            st_jira = dict_jira.get(r['Nro_Ppto_Match'], "Sin Ticket")
            
            es_corp = str(r.get('Corporativa','')).upper() == "SI"
            clase = "card-corp" if es_corp else "card-vendedor"
            
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <b>{r['Cliente']}</b> <span class="status-badge">{st_jira}</span><br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']} | {r['Facturado']}</small>
                        </div>
                        <div style="text-align:right; flex:1;">
                            <span class="monto-alerta">${r['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar Pago"):
                nv = st.number_input("Cobrado", value=float(r['Anticipo']), key=f"f{i}")
                if st.button("Guardar", key=f"b{i}"):
                    ws.update_cell(i+2, 5, nv); st.rerun()

    with col_form:
        st.subheader("📝 Nueva Venta")
        with st.form("alta", clear_on_submit=True):
            f_nro = st.text_input("Nro Presupuesto")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            f_fac = st.selectbox("Factura", ["Facturado", "Sin Facturar", "Pendiente"])
            f_tot = st.number_input("Total $", step=1.0)
            f_ant = st.number_input("Anticipo $", step=1.0)
            f_corp = st.checkbox("Cuenta Corporativa")
            if st.form_submit_button("REGISTRAR"):
                hoy = datetime.now().strftime("%Y-%m-%d")
                ws.append_row([hoy, f_nro, f_cli, f_tot, f_ant, f_ven, f_fac, hoy, "SI" if f_corp else "NO"])
                st.success("Cargado!"); st.rerun()
else:
    st.info("No hay datos.")