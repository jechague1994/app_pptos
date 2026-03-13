import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth

# --- 1. CONFIGURACIÓN ---
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
        
        # LIMPIEZA EXTREMA PARA EL MATCH
        # 1. Convertir a string. 2. Quitar el ".0" si existe. 3. Quitar espacios.
        df['Nro_Ppto_Match'] = df['Nro_Ppto'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        
        return df, ws
    except Exception as e:
        st.error(f"Error Datos: {e}")
        return pd.DataFrame(), None

def consultar_jira():
    try:
        conf = st.secrets["jira"]
        api_url = f"{conf['url'].strip().rstrip('/')}/rest/api/3/search"
        auth = HTTPBasicAuth(conf["user"], conf["token"].strip())
        params = {'jql': f'project="{conf["project_key"].strip()}"', 'fields': 'summary,status', 'maxResults': 100}
        
        res = requests.get(api_url, params=params, auth=auth, timeout=10)
        if res.status_code == 200:
            issues = res.json().get('issues', [])
            # Limpiamos el summary de Jira igual que el del Excel
            return {str(iss['fields']['summary']).replace(r'\.0$', '', regex=True).strip(): iss['fields']['status']['name'] for iss in issues}
    except:
        pass
    return {}

# --- 3. DASHBOARD ---
df, ws = cargar_datos()
dict_jira = consultar_jira()

if not df.empty:
    st.title("🚀 Gestión Magallan")
    
    # Métricas
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VENTAS TOTALES", f"${df['Monto_Total'].sum():,.0f}")
    c2.metric("COBRADO", f"${df['Anticipo'].sum():,.0f}")
    c3.metric("DEUDA", f"${df['Saldo'].sum():,.0f}")
    c4.metric("TICKETS JIRA", len(dict_jira))

    st.divider()

    col_izq, col_der = st.columns([1.5, 2])

    with col_izq:
        st.subheader("📝 Nuevo Registro")
        with st.form("alta"):
            nro = st.text_input("Nro Presupuesto (ID Jira)")
            cli = st.text_input("Cliente")
            ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            fac = st.selectbox("Condición Factura", ["Facturado", "Sin Facturar", "Pendiente"])
            f_ppto = st.date_input("Fecha Ppto")
            f_vta = st.date_input("Fecha Venta")
            tot = st.number_input("Monto Total $", step=1.0)
            ant = st.number_input("Anticipo $", step=1.0)
            corp = st.checkbox("Cuenta Corporativa")
            
            if st.form_submit_button("REGISTRAR"):
                ws.append_row([f_ppto.strftime("%Y-%m-%d"), nro, cli, tot, ant, ven, fac, f_vta.strftime("%Y-%m-%d"), "SI" if corp else "NO"])
                st.success("¡Venta cargada!"); st.rerun()

    with col_der:
        st.subheader("📑 Cartera de Pedidos")
        busc = st.text_input("🔍 Buscar por cliente o número...")
        df_v = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        for i, r in df_v.sort_values(by='Nro_Ppto', ascending=False).iterrows():
            nro_match = r['Nro_Ppto_Match']
            # Buscamos en el diccionario. Si no está, sale "Sin Ticket"
            est_j = dict_jira.get(nro_match, "Sin Ticket")
            
            es_corp = str(r.get('Corporativa','')).upper() == "SI"
            clase = "card-corp" if es_corp else "card-vendedor"
            
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <span style="font-size:1.1rem; font-weight:bold;">{r['Cliente']}</span> 
                            <span class="status-badge">🛠 {est_j}</span><br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']} | {r.get('Facturado','-')}</small>
                        </div>
                        <div style="text-align:right; flex:1;">
                            <span class="monto-alerta">${r['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar Pago"):
                nuevo_ant = st.number_input("Monto cobrado", value=float(r['Anticipo']), key=f"upd_{i}")
                if st.button("Guardar", key=f"btn_{i}"):
                    ws.update_cell(i+2, 5, nuevo_ant); st.rerun()

else:
    st.info("Sin datos para mostrar.")