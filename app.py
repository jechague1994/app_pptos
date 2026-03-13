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

# CSS para tarjetas y diseño
st.markdown("""
    <style>
    .metric-container { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; }
    .card-vendedor { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .card-corp { background: #f8fafc; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #1e293b; border: 1px solid #e2e8f0; }
    .status-badge { background: #0052CC; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.8rem; font-weight: bold; }
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
        df['Anticipo'] = pd.to_numeric(df['Anticipo'].astype(str).str.replace('.','').str.replace(',','.'), errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
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
            mapa = {}
            for iss in issues:
                # En v3 el summary a veces viene dentro de 'content' si es un doc, 
                # pero normalmente está en fields['summary']
                summary = str(iss['fields'].get('summary', ''))
                status = iss['fields']['status']['name']
                nums = re.findall(r'\d+', summary)
                for n in nums: mapa[n] = status
            return mapa
    except: return {}

# --- 3. LÓGICA ---
df, ws = cargar_datos()
dict_jira = consultar_jira()

if not df.empty:
    st.title("📊 Panel de Control Magallan")
    
    # --- SECCIÓN 1: MÉTRICAS CLAVE ---
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("TOTAL VENTAS", f"${df['Monto_Total'].sum():,.0f}")
    with m2: st.metric("TOTAL COBRADO", f"${df['Anticipo'].sum():,.0f}")
    with m3: 
        saldo_total = df['Saldo'].sum()
        st.metric("SALDO PENDIENTE", f"${saldo_total:,.0f}", delta=f"{saldo_total/df['Monto_Total'].sum()*100:.1f}% del total", delta_color="inverse")
    with m4: st.metric("PROYECTOS JIRA", len(dict_jira))

    st.divider()

    # --- SECCIÓN 2: GRÁFICOS MÚLTIPLES ---
    g1, g2, g3 = st.columns(3)

    with g1:
        # Gráfico de Ventas por Vendedor
        fig_ven = px.pie(df, values='Monto_Total', names='Vendedor', title="Ventas por Vendedor", hole=0.4)
        fig_ven.update_layout(showlegend=False)
        st.plotly_chart(fig_ven, use_container_width=True)

    with g2:
        # Gráfico de Evolución Mensual
        df_mes = df.copy()
        df_mes['Mes'] = df_mes['Fecha'].dt.strftime('%b %y')
        resumen_mes = df_mes.groupby('Mes')['Monto_Total'].sum().reset_index()
        fig_mes = px.line(resumen_mes, x='Mes', y='Monto_Total', title="Tendencia de Ventas", markers=True)
        st.plotly_chart(fig_mes, use_container_width=True)

    with g3:
        # Gráfico de Estado de Facturación
        fig_fac = px.bar(df, x='Facturado', y='Monto_Total', color='Facturado', title="Monto por Estado Factura")
        fig_fac.update_layout(showlegend=False)
        st.plotly_chart(fig_fac, use_container_width=True)

    st.divider()

    # --- SECCIÓN 3: LISTADO Y REGISTRO ---
    col_lista, col_form = st.columns([2, 1])

    with col_lista:
        st.subheader("📑 Gestión de Pedidos")
        busc = st.text_input("🔍 Filtrar cliente, vendedor o número...")
        df_f = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        for i, r in df_f.sort_values(by='Fecha', ascending=False).iterrows():
            # MATCH DINÁMICO: Jira vs Excel
            status_jira = dict_jira.get(r['Nro_Ppto_Match'], "Sin Ticket")
            clase = "card-corp" if str(r.get('Corporativa','')).upper() == "SI" else "card-vendedor"
            
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <span style="font-size:1.1rem; font-weight:bold;">{r['Cliente']}</span> 
                            <span class="status-badge">{status_jira}</span><br>
                            <small>Ppto: {r['Nro_Ppto']} | Vendedor: {r['Vendedor']} | {r['Facturado']}</small>
                        </div>
                        <div style="text-align:right;">
                            <span style="color:#64748b; font-size:0.8rem;">SALDO</span><br>
                            <span class="monto-alerta">${r['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Modificar Cobro"):
                nuevo_val = st.number_input("Total cobrado", value=float(r['Anticipo']), key=f"n_{i}")
                if st.button("Actualizar", key=f"b_{i}"):
                    ws.update_cell(i+2, 5, nuevo_val)
                    st.rerun()

    with col_form:
        st.subheader("📝 Nueva Venta")
        with st.form("form_vta", clear_on_submit=True):
            f_ppto = st.text_input("Número Ppto")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            f_fac = st.selectbox("Factura", ["Facturado", "Sin Facturar", "Pendiente"])
            f_tot = st.number_input("Total $", min_value=0.0)
            f_ant = st.number_input("Anticipo $", min_value=0.0)
            f_corp = st.checkbox("Cuenta Corporativa")
            if st.form_submit_button("GUARDAR"):
                hoy = datetime.now().strftime("%Y-%m-%d")
                ws.append_row([hoy, f_ppto, f_cli, f_tot, f_ant, f_ven, f_fac, hoy, "SI" if f_corp else "NO"])
                st.success("¡Venta registrada!")
                st.rerun()