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
st.set_page_config(page_title="Magallan Control Panel", layout="wide", page_icon="📊")

# Estilo mejorado para mayor claridad
st.markdown("""
    <style>
    .stMetric { background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
    .card-vendedor { background: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #3b82f6; box-shadow: 0 2px 5px rgba(0,0,0,0.08); }
    .card-corp { background: #f8fafc; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #1e293b; border: 1px solid #e2e8f0; }
    .status-badge { background: #0052CC; color: white; padding: 5px 14px; border-radius: 20px; font-size: 0.85rem; font-weight: 700; box-shadow: 0 2px 4px rgba(0,82,204,0.3); }
    .monto-alerta { color: #e11d48; font-weight: 800; font-size: 1.2rem; }
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
        # Identificador limpio (ej: "12423")
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
        
        # JQL para traer todo el proyecto
        params = {
            'jql': f'project="{conf["project_key"].strip()}"',
            'fields': 'summary,status',
            'maxResults': 100
        }
        
        res = requests.get(api_url, params=params, auth=auth, timeout=12)
        if res.status_code == 200:
            issues = res.json().get('issues', [])
            mapa = {}
            for iss in issues:
                summary = str(iss['fields'].get('summary', ''))
                status_name = iss['fields']['status']['name']
                # Extraemos números de 4 a 6 dígitos del título
                found_nums = re.findall(r'\b\d{4,6}\b', summary)
                for n in found_nums:
                    mapa[n] = status_name
            return mapa
    except:
        return {}

# --- 3. DASHBOARD ---
df, ws = cargar_datos()
dict_jira = consultar_jira()

if not df.empty:
    st.title("📊 Magallan Dashboard Intelligence")

    # --- MÉTRICAS SUPERIORES ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS TOTALES", f"${df['Monto_Total'].sum():,.0f}")
    m2.metric("COBRADO", f"${df['Anticipo'].sum():,.0f}")
    m3.metric("SALDO PENDIENTE", f"${df['Saldo'].sum():,.0f}", delta_color="inverse")
    m4.metric("PRODUCCIÓN (JIRA)", len(dict_jira))

    st.divider()

    # --- GRÁFICOS DINÁMICOS (ARRIBA) ---
    g1, g2 = st.columns([1, 1])

    with g1:
        # Gráfico de Ventas por Vendedor
        fig_ven = px.bar(df.groupby('Vendedor')['Monto_Total'].sum().reset_index(), 
                         x='Vendedor', y='Monto_Total', color='Vendedor',
                         title="Ventas por Vendedor ($)", template="plotly_white")
        fig_ven.update_layout(showlegend=False)
        st.plotly_chart(fig_ven, use_container_width=True)

    with g2:
        # Distribución de Deuda por Estado Factura
        fig_pie = px.pie(df, values='Saldo', names='Facturado', 
                         title="Saldo Pendiente por Estado Factura",
                         hole=.4, color_discrete_sequence=px.colors.qualitative.Safe)
        st.plotly_chart(fig_pie, use_container_width=True)

    # Gráfico de Línea de Tiempo (Ancho completo)
    df_time = df.dropna(subset=['Fecha']).sort_values('Fecha')
    df_time['Mes'] = df_time['Fecha'].dt.strftime('%b %Y')
    res_mes = df_time.groupby('Mes')[['Monto_Total', 'Anticipo']].sum().reset_index()
    fig_line = px.line(res_mes, x='Mes', y=['Monto_Total', 'Anticipo'], 
                       title="Evolución Mensual: Ventas vs Cobros", markers=True)
    st.plotly_chart(fig_line, use_container_width=True)

    st.divider()

    # --- LISTADO Y FORMULARIO (ABAJO) ---
    col_lista, col_alta = st.columns([1.8, 1.2])

    with col_lista:
        st.subheader("📑 Cartera de Pedidos")
        busc = st.text_input("🔍 Buscar cliente, número o vendedor...")
        df_f = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        for i, r in df_f.sort_values(by='Fecha', ascending=False).iterrows():
            # MATCH REFORZADO:
            nro_id = r['Nro_Ppto_Match']
            st_jira = dict_jira.get(nro_id, "Sin Ticket")
            
            clase = "card-corp" if str(r.get('Corporativa','')).upper() == "SI" else "card-vendedor"
            
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <span style="font-size:1.15rem; font-weight:bold;">{r['Cliente']}</span> 
                            <span class="status-badge">{st_jira}</span><br>
                            <small>Ppto: {r['Nro_Ppto']} | Vendedor: {r['Vendedor']} | {r['Facturado']}</small>
                        </div>
                        <div style="text-align:right;">
                            <span style="color:#64748b; font-size:0.8rem;">SALDO</span><br>
                            <span class="monto-alerta">${r['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar Pago"):
                nv = st.number_input("Total cobrado hasta hoy", value=float(r['Anticipo']), key=f"n_{i}")
                if st.button("Guardar", key=f"b_{i}"):
                    ws.update_cell(i+2, 5, nv)
                    st.rerun()

    with col_alta:
        st.subheader("📝 Registrar Venta")
        with st.form("f_alta", clear_on_submit=True):
            f_ppto = st.text_input("Número de Ppto")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            f_fac = st.selectbox("Factura", ["Facturado", "Sin Facturar", "Pendiente"])
            f_tot = st.number_input("Total $", min_value=0.0)
            f_ant = st.number_input("Anticipo $", min_value=0.0)
            f_corp = st.checkbox("Cuenta Corporativa")
            if st.form_submit_button("REGISTRAR VENTA"):
                hoy = datetime.now().strftime("%Y-%m-%d")
                ws.append_row([hoy, f_ppto, f_cli, f_tot, f_ant, f_ven, f_fac, hoy, "SI" if f_corp else "NO"])
                st.success("¡Venta cargada!")
                st.rerun()
else:
    st.info("No hay datos cargados.")