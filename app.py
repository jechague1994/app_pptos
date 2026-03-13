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
    .status-badge { background: #0052CC; color: white; padding: 3px 10px; border-radius: 15px; font-size: 0.75rem; font-weight: bold; }
    .monto-alerta { color: #e11d48; font-weight: 800; }
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
        
        # Limpieza clave: Convertimos Nro_Ppto a string limpio para comparar
        df['Nro_Ppto_Limpiado'] = df['Nro_Ppto'].astype(str).str.strip()
        
        hoy = datetime.now()
        df['Estado_Deuda'] = df.apply(lambda r: 'Viejo' if (hoy - r['Fecha']).days > 30 and r['Saldo'] > 0 else 'Joven', axis=1)
        return df, ws
    except Exception as e:
        st.error(f"Error Datos: {e}")
        return pd.DataFrame(), None

def consultar_jira():
    try:
        conf = st.secrets["jira"]
        url = f"{conf['url'].strip().rstrip('/')}/rest/api/2/search"
        auth = HTTPBasicAuth(conf["user"], conf["token"].strip())
        query = {'jql': f'project="{conf["project_key"]}"', 'fields': 'summary,status', 'maxResults': 100}
        res = requests.get(url, params=query, auth=auth, timeout=10)
        if res.status_code == 200:
            issues = res.json().get('issues', [])
            # Limpiamos el título de Jira para que el cruce sea exacto
            return {str(iss['fields']['summary']).strip(): iss['fields']['status']['name'] for iss in issues}
    except:
        pass
    return {}

# --- 3. BARRA LATERAL (DIAGNÓSTICO) ---
with st.sidebar:
    st.header("🛠 Diagnóstico Jira")
    if st.button("Ejecutar Test"):
        conf = st.secrets["jira"]
        base = conf['url'].strip().rstrip('/')
        try:
            auth = HTTPBasicAuth(conf["user"], conf["token"].strip())
            res = requests.get(f"{base}/rest/api/2/myself", auth=auth)
            if res.status_code == 200:
                st.success("✅ Conexión OK")
                search_url = f"{base}/rest/api/2/search"
                q = {'jql': f'project="{conf["project_key"]}"', 'maxResults': 5}
                res_q = requests.get(search_url, params=q, auth=auth)
                if res_q.status_code == 200:
                    tickets = res_q.json().get('issues', [])
                    st.info(f"Tickets encontrados: {len(tickets)}")
                    for t in tickets:
                        st.write(f"- {t['fields']['summary']}")
                else:
                    st.error(f"Error búsqueda: {res_q.status_code}")
            else:
                st.error(f"Error {res.status_code}")
        except Exception as e:
            st.error(f"Error: {e}")

# --- 4. DASHBOARD ---
df, ws = cargar_datos()
dict_jira = consultar_jira()

if not df.empty:
    st.title("🚀 Gestión Magallan")
    
    # Métricas
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VENTAS", f"${df['Monto_Total'].sum():,.0f}")
    c2.metric("COBRADO", f"${df['Anticipo'].sum():,.0f}")
    c3.metric("DEUDA VIEJA", f"${df[df['Estado_Deuda']=='Viejo']['Saldo'].sum():,.0f}")
    c4.metric("JIRA TICKETS", len(dict_jira))

    st.divider()

    col_izq, col_der = st.columns([1.5, 2])

    with col_izq:
        st.subheader("📝 Nuevo Pedido")
        with st.form("alta"):
            nro = st.text_input("Nro Ppto (Igual a Jira)")
            cli = st.text_input("Cliente")
            ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            fac = st.selectbox("Facturación", ["Facturado", "Sin Facturar", "Pendiente"])
            corp = st.checkbox("Cuenta Corporativa")
            f_ppto = st.date_input("Fecha Ppto")
            f_vta = st.date_input("Fecha Venta")
            tot = st.number_input("Total $", step=1.0)
            ant = st.number_input("Anticipo $", step=1.0)
            
            if st.form_submit_button("GUARDAR"):
                ws.append_row([f_ppto.strftime("%Y-%m-%d"), nro, cli, tot, ant, ven, fac, f_vta.strftime("%Y-%m-%d"), "SI" if corp else "NO"])
                st.success("Cargado!"); st.rerun()

    with col_der:
        st.subheader("📑 Cartera de Clientes")
        busc = st.text_input("🔍 Buscar...")
        df_v = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        for i, r in df_v.sort_values(by='Fecha', ascending=False).iterrows():
            # Buscamos usando el Nro_Ppto limpiado
            nro_limpio = str(r['Nro_Ppto_Limpiado'])
            est_j = dict_jira.get(nro_limpio, "Sin Ticket")
            
            es_corp = str(r.get('Corporativa','')).upper() == "SI"
            clase = "card-corp" if es_corp else "card-vendedor"
            
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between;">
                        <div style="flex:2;">
                            <b>{r['Cliente']}</b> <span class="status-badge">🛠 {est_j}</span><br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']} | {r.get('Facturado','-')}</small><br>
                            <small>📅 {r['Fecha'].strftime('%d/%m/%Y') if pd.notnull(r['Fecha']) else ''}</small>
                        </div>
                        <div style="text-align:right; flex:1;">
                            <span class="monto-alerta">${r['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar"):
                nuevo = st.number_input("Cobrado", value=float(r['Anticipo']), key=f"u{i}")
                if st.button("OK", key=f"b{i}"):
                    ws.update_cell(i+2, 5, nuevo); st.rerun()

    # Gráfico mensual
    df_graf = df.dropna(subset=['Fecha']).copy()
    df_graf['Mes'] = df_graf['Fecha'].dt.strftime('%Y-%m')
    fig = px.line(df_graf.groupby('Mes')['Monto_Total'].sum().reset_index(), x='Mes', y='Monto_Total', title="Ventas por Mes", markers=True)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No hay datos cargados.")