import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime, timedelta
import requests
from requests.auth import HTTPBasicAuth

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Magallan Sistema Integrado", layout="wide", page_icon="🚀")

# Estilos CSS avanzados
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .metric-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-top: 4px solid #3b82f6; }
    .card-vendedor { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .card-corp { background: #f1f5f9; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #1e293b; border: 1px solid #cbd5e1; }
    .status-badge { background: #e2e8f0; color: #475569; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
    .monto-alerta { color: #e11d48; font-weight: bold; }
    .monto-ok { color: #10b981; font-weight: bold; }
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
        
        # Procesamiento de Fechas y Números
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        
        # Clasificación de Deuda (Jóvenes < 30 días, Viejos > 30 días)
        hoy = datetime.now()
        df['Antiguedad'] = (hoy - df['Fecha']).dt.days
        df['Tipo_Deuda'] = df.apply(lambda r: 'Viejo' if r['Antiguedad'] > 30 and r['Saldo'] > 0 else 'Joven', axis=1)
        
        return df, ws
    except Exception as e:
        st.error(f"Error Sheets: {e}")
        return pd.DataFrame(), None

def consultar_jira():
    try:
        conf = st.secrets["jira"]
        url = f"{conf['url']}/rest/api/3/search"
        auth = HTTPBasicAuth(conf["user"], conf["token"])
        # Traemos todos los tickets del proyecto FAB
        query = {'jql': f'project="{conf["project_key"]}"', 'fields': 'summary,status'}
        res = requests.get(url, params=query, auth=auth, timeout=7)
        if res.status_code == 200:
            issues = res.json().get('issues', [])
            # Limpiamos el summary para que coincida con el número del Excel
            return {str(iss['fields']['summary']).replace("MAG-","").strip(): iss['fields']['status']['name'] for iss in issues}
    except:
        return {}
    return {}

# --- 3. LÓGICA DE NEGOCIO ---

df, ws = cargar_datos()
dict_jira = consultar_jira()

if not df.empty:
    # Título y Métricas Principales
    st.title("🚀 Sistema Magallan Integrado")
    
    col1, col2, col3, col4 = st.columns(4)
    total_vta = df['Monto_Total'].sum()
    total_cob = df['Anticipo'].sum()
    total_pen = df['Saldo'].sum()
    
    col1.metric("VENTAS TOTALES", f"${total_vta:,.0f}")
    col2.metric("COBRADO", f"${total_cob:,.0f}", f"{(total_cob/total_vta)*100:.1f}%")
    col3.metric("DEUDA TOTAL", f"${total_pen:,.0f}", delta_color="inverse")
    col4.metric("TICKETS JIRA", len(dict_jira))

    # --- SECCIÓN DE SALDOS (Jóvenes vs Viejos) ---
    st.subheader("⏳ Análisis de Antigüedad de Deuda")
    c_jov, c_vie = st.columns(2)
    
    deuda_joven = df[df['Tipo_Deuda'] == 'Joven']['Saldo'].sum()
    deuda_vieja = df[df['Tipo_Deuda'] == 'Viejo']['Saldo'].sum()
    
    with c_jov:
        st.markdown(f"""<div class='metric-card'><h4>Saldos Jóvenes (<30 días)</h4><h2 style='color:#3b82f6;'>${deuda_joven:,.0f}</h2></div>""", unsafe_allow_html=True)
    with c_vie:
        st.markdown(f"""<div class='metric-card' style='border-top-color:#e11d48;'><h4>Saldos Viejos (>30 días)</h4><h2 style='color:#e11d48;'>${deuda_vieja:,.0f}</h2></div>""", unsafe_allow_html=True)

    st.divider()

    # --- CUERPO PRINCIPAL ---
    col_reg, col_list = st.columns([1, 2])

    with col_reg:
        st.subheader("📝 Nuevo Registro")
        with st.form("form_alta", clear_on_submit=True):
            f_nro = st.text_input("MAG# (Número)")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            f_corp = st.checkbox("¿Es Corporativo?")
            f_tot = st.number_input("Total ($)", step=1.0)
            f_ant = st.number_input("Anticipo ($)", step=1.0)
            f_fec = st.date_input("Fecha", datetime.now())
            if st.form_submit_button("REGISTRAR"):
                nueva = [f_fec.strftime("%Y-%m-%d"), f_nro, f_cli, f_tot, f_ant, f_ven, "No", f_fec.strftime("%Y-%m-%d"), "SI" if f_corp else "NO"]
                ws.append_row(nueva)
                st.success("Guardado!")
                st.rerun()

    with col_list:
        st.subheader("📑 Cartera y Taller")
        busc = st.text_input("🔍 Buscar por cliente o número...")
        
        df_f = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        for i, fila in df_f.sort_values(by='Fecha', ascending=False).iterrows():
            # Match con Jira
            nro_id = str(fila['Nro_Ppto']).strip()
            st_jira = dict_jira.get(nro_id, "Sin Ticket")
            
            es_corp = str(fila['Corporativa']).upper() == "SI"
            clase_monto = "monto-ok" if fila['Saldo'] <= 0 else "monto-alerta"
            color_deuda = "🔴" if fila['Tipo_Deuda'] == 'Viejo' else "🔵"
            
            st.markdown(f"""
                <div class="{'card-corp' if es_corp else 'card-vendedor'}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <b>MAG-{nro_id} | {fila['Cliente']}</b> <span class="status-badge">🛠 {st_jira}</span><br>
                            <small>{color_deuda} {fila['Vendedor']} | {fila['Fecha'].strftime('%d/%m/%Y') if not pd.isnull(fila['Fecha']) else 'S/F'}</small>
                        </div>
                        <div style="text-align:right;">
                            <small>SALDO</small><br>
                            <span class="{clase_monto}">${fila['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar Pagos"):
                new_ant = st.number_input("Cobrado total", value=float(fila['Anticipo']), key=f"upd_{i}")
                if st.button("Guardar", key=f"btn_{i}"):
                    ws.update_cell(i+2, 5, new_ant)
                    st.rerun()

    # --- 4. GRÁFICOS ---
    st.divider()
    st.subheader("📊 Gráficos de Gestión")
    ga, gb = st.columns(2)
    with ga:
        fig1 = px.pie(df, values='Saldo', names='Tipo_Deuda', title="Distribución de Deuda (Joven vs Vieja)", color_discrete_sequence=['#3b82f6', '#e11d48'])
        st.plotly_chart(fig1, use_container_width=True)
    with gb:
        fig2 = px.bar(df.groupby('Vendedor')['Monto_Total'].sum().reset_index(), x='Vendedor', y='Monto_Total', title="Ventas por Vendedor")
        st.plotly_chart(fig2, use_container_width=True)

else:
    st.warning("Conectado pero sin datos. Verifica la pestaña 'Saldos_Simples'.")