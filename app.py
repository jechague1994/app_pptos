import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Magallan Sistema Integrado", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .card-vendedor { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .card-corp { background: #f1f5f9; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #1e293b; border: 1px solid #cbd5e1; }
    .status-badge { background: #0052CC; color: white; padding: 3px 10px; border-radius: 15px; font-size: 0.75rem; font-weight: bold; }
    .monto-alerta { color: #e11d48; font-weight: 800; font-size: 1.2rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCIONES DE CONEXIÓN ---

@st.cache_resource(ttl=60)
def conectar_gs():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error Google Sheets: {e}")
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
        
        # Envejecimiento de deuda
        hoy = datetime.now()
        df['Antiguedad'] = (hoy - df['Fecha']).dt.days
        df['Estado_Deuda'] = df.apply(lambda r: 'Viejo' if r['Antiguedad'] > 30 and r['Saldo'] > 0 else 'Joven', axis=1)
        return df, ws
    except Exception as e:
        st.error(f"Error al leer Excel: {e}")
        return pd.DataFrame(), None

# --- ESTA ES LA PARTE QUE DEBES REVISAR ---
def consultar_jira():
    try:
        conf = st.secrets["jira"]
        # Limpieza de URL para evitar Error 410
        base_url = conf['url'].strip().rstrip('/')
        api_url = f"{base_url}/rest/api/2/search"
        
        auth = HTTPBasicAuth(conf["user"], conf["token"].strip())
        
        query = {
            'jql': f'project="{conf["project_key"]}"',
            'fields': 'summary,status',
            'maxResults': 100
        }
        
        res = requests.get(api_url, params=query, auth=auth, timeout=10)
        
        if res.status_code == 200:
            issues = res.json().get('issues', [])
            # Mapeo directo: lo que dice el título del ticket = Estado
            return {str(iss['fields']['summary']).strip(): iss['fields']['status']['name'] for iss in issues}
        else:
            st.sidebar.error(f"Jira Error {res.status_code}. Revisa la URL en Secrets.")
            return {}
    except Exception as e:
        st.sidebar.warning(f"Error de red Jira: {e}")
        return {}

# --- 3. LÓGICA DE LA APP ---

df, ws = cargar_datos()
dict_jira = consultar_jira()

if not df.empty:
    st.title("🚀 Magallan Sistema Integrado")
    
    # Métricas superiores
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("VENTAS TOTALES", f"${df['Monto_Total'].sum():,.0f}")
    t2.metric("COBRADO", f"${df['Anticipo'].sum():,.0f}")
    t3.metric("DEUDA VIEJA (>30d)", f"${df[df['Estado_Deuda']=='Viejo']['Saldo'].sum():,.0f}")
    t4.metric("TICKETS TALLER", len(dict_jira))

    st.divider()

    col_reg, col_list = st.columns([1.4, 2])

    with col_reg:
        st.subheader("📝 Nuevo Registro")
        with st.form("form_alta", clear_on_submit=True):
            f_nro = st.text_input("Nro de Ppto (ID Jira)")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            f_fact = st.selectbox("Condición Factura", ["Facturado", "Sin Facturar", "Pendiente"])
            f_corp = st.checkbox("¿Es Cuenta Corporativa?")
            
            c1, c2 = st.columns(2)
            f_fec_ppto = c1.date_input("Fecha Ppto", datetime.now())
            f_fec_vta = c2.date_input("Fecha Venta", datetime.now())
            
            f_tot = st.number_input("Monto Total ($)", step=1.0)
            f_ant = st.number_input("Anticipo Recibido ($)", step=1.0)
            
            if st.form_submit_button("REGISTRAR VENTA"):
                nueva_fila = [
                    f_fec_ppto.strftime("%Y-%m-%d"), f_nro, f_cli, f_tot, f_ant, 
                    f_ven, f_fact, f_fec_vta.strftime("%Y-%m-%d"), "SI" if f_corp else "NO"
                ]
                ws.append_row(nueva_fila)
                st.success("¡Venta registrada!")
                st.rerun()

    with col_list:
        st.subheader("📑 Cartera y Taller")
        busc = st.text_input("🔍 Buscar cliente o número...")
        df_f = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        for i, fila in df_f.sort_values(by='Fecha', ascending=False).iterrows():
            nro_id = str(fila['Nro_Ppto']).strip()
            est_jira = dict_jira.get(nro_id, "Sin Ticket")
            
            es_corp = str(fila.get('Corporativa', 'NO')).upper() == "SI"
            
            st.markdown(f"""
                <div class="{'card-corp' if es_corp else 'card-vendedor'}">
                    <div style="display:flex; justify-content:space-between;">
                        <div>
                            <b>{fila['Cliente']}</b> <span class="status-badge">{est_jira}</span><br>
                            <small>Ppto: {nro_id} | {fila['Vendedor']} | Fact: {fila.get('Facturado', 'S/F')}</small><br>
                            <small>📅 Venta: {fila['Fecha'].strftime('%d/%m/%Y') if pd.notnull(fila['Fecha']) else 'S/F'}</small>
                        </div>
                        <div style="text-align:right;">
                            <small>SALDO</small><br>
                            <span class="monto-alerta">${fila['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar Cobro"):
                nuevo_pago = st.number_input("Total cobrado", value=float(fila['Anticipo']), key=f"upd_{i}")
                if st.button("Guardar", key=f"btn_{i}"):
                    ws.update_cell(i+2, 5, nuevo_pago)
                    st.rerun()

    # --- 4. GRÁFICO MENSUAL ---
    st.divider()
    df_mes = df.copy()
    df_mes['Mes'] = df_mes['Fecha'].dt.strftime('%Y-%m')
    df_grafico = df_mes.groupby('Mes')['Monto_Total'].sum().reset_index()
    fig = px.line(df_grafico, x='Mes', y='Monto_Total', title="Evolución de Ventas Mensuales ($)", markers=True)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("Verifica la conexión a Google Sheets o el nombre de la pestaña.")