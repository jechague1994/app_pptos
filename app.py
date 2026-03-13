import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Magallan ERP + Jira", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8FAFC; }
    .card-vendedor { background: white; border: 1px solid #E2E8F0; border-left: 6px solid #0284C7; border-radius: 12px; padding: 18px; margin-bottom: 12px; }
    .card-corp { background: #F1F5F9; border: 1px solid #CBD5E1; border-left: 6px solid #1E293B; border-radius: 12px; padding: 18px; margin-bottom: 12px; }
    .monto-deuda { color: #E11D48; font-size: 1.2rem; font-weight: 800; }
    .monto-ok { color: #10B981; font-size: 1.2rem; font-weight: 800; }
    .tag { padding: 3px 8px; border-radius: 5px; font-size: 0.7rem; font-weight: 700; margin-right: 5px; }
    .tag-jira { background: #E9ECEF; color: #495057; border: 1px solid #CED4DA; }
    .tag-vend { background: #EEF2FF; color: #4338CA; }
    .tag-corp { background: #1E293B; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIONES (GOOGLE & JIRA) ---
@st.cache_resource(ttl=60)
def conectar_gs():
    try:
        return gspread.authorize(Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        ))
    except: return None

def obtener_datos_excel():
    gc = conectar_gs()
    if not gc: return pd.DataFrame(), None
    try:
        sh = gc.open("Gestion_Magallan")
        ws = sh.worksheet("Saldos_Simples")
        df = pd.DataFrame(ws.get_all_records())
        # Blindaje de columnas
        cols = ['Fecha', 'Nro_Ppto', 'Cliente', 'Monto_Total', 'Anticipo', 'Vendedor', 'Facturado', 'Fecha_Confirmacion', 'Corporativa']
        for c in cols:
            if c not in df.columns: df[c] = ""
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df['Fecha_Confirmacion'] = pd.to_datetime(df['Fecha_Confirmacion'], errors='coerce')
        df['Es_Corp'] = df['Corporativa'].apply(lambda x: str(x).upper() == "SI")
        df['Origen'] = df.apply(lambda r: "CORPORATIVO" if r['Es_Corp'] else r['Vendedor'], axis=1)
        return df, ws
    except: return pd.DataFrame(), None

def obtener_jira():
    try:
        url = f"{st.secrets['jira']['url']}/rest/api/3/search"
        auth = HTTPBasicAuth(st.secrets['jira']['user'], st.secrets['jira']['token'])
        query = {'jql': f'project = "{st.secrets["jira"]["project_key"]}"', 'fields': 'summary,status'}
        res = requests.get(url, headers={"Accept": "application/json"}, params=query, auth=auth)
        if res.status_code == 200:
            issues = res.json().get('issues', [])
            # Diccionario: { '1234': 'In Progress' } (limpiamos el MAG- del summary si hace falta)
            return {issue['fields']['summary'].replace("MAG-","").strip(): issue['fields']['status']['name'] for issue in issues}
    except: return {}
    return {}

# --- 3. LOGICA PRINCIPAL ---
df, ws = obtener_datos_excel()
dict_jira = obtener_jira()

if not df.empty:
    st.title("📊 Magallan ERP + Tablero Jira FAB")

    # Métricas Superiores
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS TOTALES", f"${df['Monto_Total'].sum():,.0f}")
    m2.metric("COBRADO", f"${df['Anticipo'].sum():,.0f}")
    m3.metric("PENDIENTE", f"${df['Saldo'].sum():,.0f}", delta_color="inverse")
    m4.metric("TICKETS EN JIRA", f"{len(dict_jira)} Activos")

    # --- SECCIÓN DE GRÁFICOS ---
    st.subheader("📈 Análisis de Gestión y Taller")
    g1, g2, g3 = st.columns(3)

    with g1:
        # Cobranza por Vendedor/Corp
        rend = df.groupby('Origen').agg({'Anticipo':'sum', 'Saldo':'sum'}).reset_index()
        st.plotly_chart(px.bar(rend, x='Origen', y=['Anticipo', 'Saldo'], title="Cobranza por Origen", barmode='group', color_discrete_map={'Anticipo':'#10B981', 'Saldo':'#E11D48'}), use_container_width=True)

    with g2:
        # Carga del Taller (Datos de Jira)
        if dict_jira:
            df_jira = pd.DataFrame(list(dict_jira.items()), columns=['ID', 'Estado'])
            st.plotly_chart(px.pie(df_jira, names='Estado', title="Carga del Taller (Jira)", hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe), use_container_width=True)
        else:
            st.info("Sin datos de Jira")

    with g3:
        # Perfil Corporativo
        fig_pie = px.pie(df, values='Monto_Total', names='Origen', title="Participación en Ventas")
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # --- LISTADO CON INTEGRACIÓN JIRA ---
    st.subheader("📋 Gestión de Saldos y Producción")
    busc = st.text_input("🔍 Buscar cliente, Nro de presupuesto o estado...")
    
    # Ordenar y filtrar
    df_list = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
    
    for i, r in df_list.sort_values(by='Fecha', ascending=False).iterrows():
        # Cruzar con Jira
        estado_taller = dict_jira.get(str(r['Nro_Ppto']).strip(), "No en Tablero")
        estilo = "card-corp" if r['Es_Corp'] else "card-vendedor"
        
        st.markdown(f"""
            <div class="{estilo}">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-size:0.8rem; color:#64748B;">Ppto: {r['Fecha'].strftime('%d/%m/%y') if not pd.isnull(r['Fecha']) else 'S/F'}</span><br>
                        <b style="font-size:1.1rem;">MAG-{r['Nro_Ppto']} | {r['Cliente']}</b>
                        <span class="tag tag-jira">⚙️ {estado_taller}</span><br>
                        <span class="tag {'tag-corp' if r['Es_Corp'] else 'tag-vend'}">{"CORPORATIVO" if r['Es_Corp'] else r['Vendedor']}</span>
                        <span class="tag tag-fact">{r['Facturado']}</span>
                    </div>
                    <div class="{'monto-ok' if r['Saldo']<=0 else 'monto-deuda'}">
                        {'$' + str(f"{r['Saldo']:,.0f}") if r['Saldo']>0 else 'SALDADO'}
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        with st.expander("Actualizar montos"):
            col_u1, col_u2 = st.columns(2)
            ut = col_u1.number_input("Total", value=float(r['Monto_Total']), key=f"t{i}")
            ua = col_u2.number_input("Anticipo", value=float(r['Anticipo']), key=f"a{i}")
            if st.button("Guardar Cambios", key=f"b{i}"):
                ws.update_cell(i+2, 4, ut)
                ws.update_cell(i+2, 5, ua)
                st.rerun()