import streamlit as st
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
        
        # Procesamiento de Datos
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        
        # Identificador limpio para Jira
        df['Nro_Ppto_Match'] = df['Nro_Ppto'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        
        # Envejecimiento
        hoy = datetime.now()
        df['Estado_Deuda'] = df.apply(lambda r: 'Viejo' if (hoy - r['Fecha']).days > 30 and r['Saldo'] > 0 else 'Joven', axis=1)
        
        return df, ws
    except Exception as e:
        st.error(f"Error al cargar Excel: {e}")
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
            # Guardamos los tickets
            return issues
    except:
        pass
    return []

# --- 3. LÓGICA DE MATCHING INTELIGENTE ---
def obtener_estado_jira(nro_ppto, lista_tickets):
    if not nro_ppto or nro_ppto == "None":
        return "Sin ID"
    
    for ticket in lista_tickets:
        summary = str(ticket['fields']['summary']).strip()
        # Si el número de presupuesto está contenido en cualquier parte del título del ticket
        if nro_ppto in summary:
            return ticket['fields']['status']['name']
    
    return "Sin Ticket"

# --- 4. DASHBOARD ---
df, ws = cargar_datos()
tickets_jira = consultar_jira()

if not df.empty:
    st.title("🚀 Magallan: Sistema de Gestión Integrado")
    
    # MÉTRICAS PRINCIPALES
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS TOTALES", f"${df['Monto_Total'].sum():,.0f}")
    m2.metric("COBRADO", f"${df['Anticipo'].sum():,.0f}")
    m3.metric("DEUDA VIEJA (>30d)", f"${df[df['Estado_Deuda']=='Viejo']['Saldo'].sum():,.0f}", delta_color="inverse")
    m4.metric("PRODUCCIÓN (JIRA)", len(tickets_jira))

    st.divider()

    col_reg, col_list = st.columns([1.3, 2])

    with col_reg:
        st.subheader("📝 Nuevo Registro")
        with st.form("form_alta", clear_on_submit=True):
            f_nro = st.text_input("Nro Presupuesto (ID Jira)")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            f_fact = st.selectbox("Condición Factura", ["Facturado", "Sin Facturar", "Pendiente"])
            
            c1, c2 = st.columns(2)
            f_fec_ppto = c1.date_input("Fecha Ppto", datetime.now())
            f_fec_vta = c2.date_input("Fecha Venta", datetime.now())
            
            f_tot = st.number_input("Monto Total $", step=100.0)
            f_ant = st.number_input("Anticipo $", step=100.0)
            f_corp = st.checkbox("¿Es Cuenta Corporativa?")
            
            if st.form_submit_button("REGISTRAR VENTA"):
                nueva_fila = [
                    f_fec_ppto.strftime("%Y-%m-%d"), f_nro, f_cli, f_tot, f_ant, 
                    f_ven, f_fact, f_fec_vta.strftime("%Y-%m-%d"), "SI" if f_corp else "NO"
                ]
                ws.append_row(nueva_fila)
                st.success("Venta guardada!")
                st.rerun()

    with col_list:
        st.subheader("📑 Cartera de Pedidos")
        busc = st.text_input("🔍 Buscar cliente o ppto...")
        df_f = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        # Mostrar tarjetas
        for i, r in df_f.sort_values(by='Nro_Ppto', ascending=False).iterrows():
            # Buscamos estado en Jira con lógica flexible
            estado_actual = obtener_estado_jira(r['Nro_Ppto_Match'], tickets_jira)
            
            es_corp = str(r.get('Corporativa', 'NO')).upper() == "SI"
            clase = "card-corp" if es_corp else "card-vendedor"
            
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <span style="font-size:1.1rem; font-weight:bold;">{r['Cliente']}</span> 
                            <span class="status-badge">{estado_actual}</span><br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']} | {r.get('Facturado', 'S/F')}</small><br>
                            <small>📅 Venta: {r['Fecha'].strftime('%d/%m/%Y') if pd.notnull(r['Fecha']) else 'S/F'}</small>
                        </div>
                        <div style="text-align:right; flex:1;">
                            <small>SALDO</small><br>
                            <span class="monto-alerta">${r['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar Cobro"):
                nuevo_pago = st.number_input("Total cobrado", value=float(r['Anticipo']), key=f"upd_{i}")
                if st.button("Guardar", key=f"btn_{i}"):
                    ws.update_cell(i+2, 5, nuevo_pago)
                    st.rerun()

    # --- 5. GRÁFICOS DE CONTROL ---
    st.divider()
    st.subheader("📊 Análisis de Ventas Mensuales")
    df_graf = df.dropna(subset=['Fecha']).copy()
    df_graf['Mes'] = df_graf['Fecha'].dt.strftime('%Y-%m')
    df_resumen = df_graf.groupby('Mes')['Monto_Total'].sum().reset_index()
    
    fig = px.bar(df_resumen, x='Mes', y='Monto_Total', 
                 title="Ventas por Mes ($)",
                 color_discrete_sequence=['#3b82f6'])
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("No hay datos cargados. Revisa la pestaña 'Saldos_Simples' en tu Excel.")