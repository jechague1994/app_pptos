[12:52, 13/3/2026] Jonathan: import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
import re

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Magallan Sistema Integrado", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .card-vendedor { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .card-corp { background: #f1f5f9; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #1e293b; border: 1px solid #cbd5e1; }
    .stat…
[13:00, 13/3/2026] Jonathan: import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Magallan Sistema Integrado", layout="wide", page_icon="🚀")

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
        # Match ultra-limpio
        df['Nro_Ppto_Match'] = df['Nro_Ppto'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        
        hoy = datetime.now()
        df['Estado_Deuda'] = df.apply(lambda r: 'Viejo' if (hoy - r['Fecha']).days > 30 and r['Saldo'] > 0 else 'Joven', axis=1)
        return df, ws
    except Exception as e:
        st.error(f"Error Datos: {e}")
        return pd.DataFrame(), None

def consultar_jira():
    try:
        conf = st.secrets["jira"]
        api_url = f"{conf['url'].strip().rstrip('/')}/rest/api/3/search"
        auth = HTTPBasicAuth(conf["user"], conf["token"].strip())
        
        # Traemos todos los tickets del proyecto para comparar localmente (más rápido)
        params = {
            'jql': f'project="{conf["project_key"].strip()}"',
            'fields': 'summary,status',
            'maxResults': 100
        }
        
        res = requests.get(api_url, params=params, auth=auth, timeout=10)
        if res.status_code == 200:
            issues = res.json().get('issues', [])
            # Mapeo: Si el número está en el título, guardamos el estado
            # Clave: número (texto), Valor: estado
            mapa_estados = {}
            for iss in issues:
                summary = str(iss['fields']['summary']).lower()
                status = iss['fields']['status']['name']
                # Buscamos patrones numéricos de 4 o 5 dígitos en el título
                nums = re.findall(r'\d+', summary)
                for n in nums:
                    mapa_estados[n] = status
            return mapa_estados
    except:
        pass
    return {}

import re # Necesario para la limpieza

# --- 3. DASHBOARD (GRÁFICOS ARRIBA) ---
df, ws = cargar_datos()
dict_jira = consultar_jira()

if not df.empty:
    st.title("🚀 Panel de Control Magallan")
    
    # MÉTRICAS Y GRÁFICOS (ARRIBA)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS TOTALES", f"${df['Monto_Total'].sum():,.0f}")
    m2.metric("COBRADO", f"${df['Anticipo'].sum():,.0f}")
    m3.metric("DEUDA VIEJA", f"${df[df['Estado_Deuda']=='Viejo']['Saldo'].sum():,.0f}")
    m4.metric("TICKETS JIRA", len(dict_jira))

    # Gráfico de ventas arriba
    df_graf = df.dropna(subset=['Fecha']).copy()
    df_graf['Mes'] = df_graf['Fecha'].dt.strftime('%Y-%m')
    resumen_mes = df_graf.groupby('Mes')['Monto_Total'].sum().reset_index()
    fig = px.bar(resumen_mes, x='Mes', y='Monto_Total', title="Ventas Mensuales ($)", color_discrete_sequence=['#3b82f6'])
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # FORMULARIO Y LISTADO (ABAJO)
    col_izq, col_der = st.columns([1.3, 2])

    with col_izq:
        st.subheader("📝 Registrar Venta")
        with st.form("alta_form"):
            nro = st.text_input("Nro Presupuesto")
            cli = st.text_input("Cliente")
            ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            fac = st.selectbox("Factura", ["Facturado", "Sin Facturar", "Pendiente"])
            tot = st.number_input("Monto Total", step=1.0)
            ant = st.number_input("Anticipo", step=1.0)
            corp = st.checkbox("Corporativa")
            if st.form_submit_button("GUARDAR"):
                ws.append_row([datetime.now().strftime("%Y-%m-%d"), nro, cli, tot, ant, ven, fac, datetime.now().strftime("%Y-%m-%d"), "SI" if corp else "NO"])
                st.success("Guardado!"); st.rerun()

    with col_der:
        st.subheader("📑 Pedidos en Curso")
        busc = st.text_input("🔍 Buscar...")
        df_v = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        for i, r in df_v.sort_values(by='Nro_Ppto', ascending=False).iterrows():
            nro_match = r['Nro_Ppto_Match']
            # Lógica de Jira: Buscamos el número en nuestro mapa
            est_j = dict_jira.get(nro_match, "Sin Ticket")
            
            clase = "card-corp" if str(r.get('Corporativa','')).upper() == "SI" else "card-vendedor"
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <b>{r['Cliente']}</b> <span class="status-badge">{est_j}</span><br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']}</small>
                        </div>
                        <div style="text-align:right;">
                            <span class="monto-alerta">${r['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar Pago"):
                nuevo = st.number_input("Cobrado", value=float(r['Anticipo']), key=f"p{i}")
                if st.button("OK", key=f"b{i}"):
                    ws.update_cell(i+2, 5, nuevo); st.rerun()
else:
    st.info("Carga datos en el Excel.")