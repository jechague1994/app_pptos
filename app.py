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
        
        # Limpieza de fechas y números
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        
        # Match ultra-limpio para evitar el .0 de Excel
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
        
        # JQL para traer tickets abiertos o recientes
        params = {
            'jql': f'project="{conf["project_key"].strip()}"',
            'fields': 'summary,status',
            'maxResults': 100
        }
        
        res = requests.get(api_url, params=params, auth=auth, timeout=10)
        if res.status_code == 200:
            issues = res.json().get('issues', [])
            mapa_estados = {}
            for iss in issues:
                summary = str(iss['fields']['summary'])
                status = iss['fields']['status']['name']
                # Buscamos cualquier número en el título del ticket
                nums_en_ticket = re.findall(r'\d+', summary)
                for n in nums_en_ticket:
                    mapa_estados[n] = status
            return mapa_estados
    except:
        pass
    return {}

# --- EJECUCIÓN ---
df, ws = cargar_datos()
dict_jira = consultar_jira()

if not df.empty:
    st.title("🚀 Panel de Control Magallan")
    
    # --- BLOQUE 1: GRÁFICOS Y MÉTRICAS (ARRIBA) ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS TOTALES", f"${df['Monto_Total'].sum():,.0f}")
    m2.metric("COBRADO", f"${df['Anticipo'].sum():,.0f}")
    m3.metric("DEUDA VIEJA (>30d)", f"${df[df['Estado_Deuda']=='Viejo']['Saldo'].sum():,.0f}")
    m4.metric("TICKETS EN JIRA", len(dict_jira))

    # Gráfico de ventas
    df_graf = df.dropna(subset=['Fecha']).copy()
    df_graf['Mes'] = df_graf['Fecha'].dt.strftime('%Y-%m')
    resumen_mes = df_graf.groupby('Mes')['Monto_Total'].sum().reset_index().sort_values('Mes')
    
    fig = px.bar(resumen_mes, x='Mes', y='Monto_Total', 
                 title="Histórico de Ventas Mensuales",
                 labels={'Monto_Total': 'Monto ($)', 'Mes': 'Mes de Venta'},
                 color_discrete_sequence=['#3b82f6'])
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- BLOQUE 2: OPERACIONES (ABAJO) ---
    col_der, col_izq = st.columns([2, 1.3]) # Invertido para mejor flujo visual

    with col_der:
        st.subheader("📑 Pedidos y Producción")
        busc = st.text_input("🔍 Buscar por cliente o presupuesto...")
        
        # Filtrado
        df_v = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        # Listado de tarjetas
        for i, r in df_v.sort_values(by='Fecha', ascending=False).iterrows():
            nro_match = r['Nro_Ppto_Match']
            # Cruce con Jira:
            est_j = dict_jira.get(nro_match, "Sin Ticket")
            
            clase = "card-corp" if str(r.get('Corporativa','')).upper() == "SI" else "card-vendedor"
            
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <b>{r['Cliente']}</b> <span class="status-badge">🛠 {est_j}</span><br>
                            <small>Ppto: {r['Nro_Ppto']} | Vendedor: {r['Vendedor']} | {r.get('Facturado','-')}</small>
                        </div>
                        <div style="text-align:right; flex:1;">
                            <small>SALDO PENDIENTE</small><br>
                            <span class="monto-alerta">${r['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander(f"Actualizar saldo de {r['Cliente']}"):
                nuevo = st.number_input("Monto total cobrado", value=float(r['Anticipo']), key=f"p_{i}")
                if st.button("Guardar Cambios", key=f"b_{i}"):
                    # +2 porque gspread es base 1 y hay encabezado
                    ws.update_cell(i+2, 5, nuevo)
                    st.success("¡Saldo actualizado!")
                    st.rerun()

    with col_izq:
        st.subheader("📝 Registrar Nueva Venta")
        with st.form("alta_form", clear_on_submit=True):
            f_nro = st.text_input("Número de Presupuesto")
            f_cli = st.text_input("Nombre del Cliente")
            f_ven = st.selectbox("Vendedor Responsable", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            f_fac = st.selectbox("Estado de Factura", ["Facturado", "Sin Facturar", "Pendiente"])
            
            c1, c2 = st.columns(2)
            f_tot = c1.number_input("Monto Total $", min_value=0.0, step=100.0)
            f_ant = c2.number_input("Anticipo $", min_value=0.0, step=100.0)
            
            f_corp = st.checkbox("¿Es Cuenta Corporativa?")
            
            if st.form_submit_button("REGISTRAR EN SISTEMA"):
                hoy_str = datetime.now().strftime("%Y-%m-%d")
                ws.append_row([hoy_str, f_nro, f_cli, f_tot, f_ant, f_ven, f_fac, hoy_str, "SI" if f_corp else "NO"])
                st.balloons()
                st.rerun()

else:
    st.info("Conectado. Esperando datos del Excel...")