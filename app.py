import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Magallan Sistema Integrado", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    .stApp { background-color: #F1F5F9; }
    .card-vendedor { 
        background: white; border-radius: 10px; padding: 15px; margin-bottom: 12px; 
        border-left: 6px solid #3B82F6; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .card-corp { 
        background: #F8FAFC; border-radius: 10px; padding: 15px; margin-bottom: 12px; 
        border-left: 6px solid #1E293B; border: 1px solid #CBD5E1;
    }
    .monto-deuda { color: #E11D48; font-size: 1.2rem; font-weight: 800; text-align: right; }
    .monto-ok { color: #10B981; font-size: 1.2rem; font-weight: 800; text-align: right; }
    .tag-jira { 
        background: #E2E8F0; color: #475569; padding: 2px 8px; border-radius: 5px; 
        font-size: 0.75rem; font-weight: bold; border: 1px solid #94A3B8;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCIONES DE DATOS ---

@st.cache_resource(ttl=60)
def conectar_gs():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(
            info, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error de credenciales: {e}")
        return None

def cargar_todo():
    gc = conectar_gs()
    if not gc: return pd.DataFrame(), None
    try:
        sh = gc.open("Gestion_Magallan")
        ws = sh.worksheet("Saldos_Simples")
        df = pd.DataFrame(ws.get_all_records())
        
        # Procesamiento numérico
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        
        # Origen para gráficos
        df['Origen'] = df.apply(lambda r: "CORPORATIVO" if str(r['Corporativa']).upper() == "SI" else r['Vendedor'], axis=1)
        
        return df, ws
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame(), None

def consultar_jira():
    try:
        conf = st.secrets["jira"]
        auth = HTTPBasicAuth(conf["user"], conf["token"])
        # Buscamos tickets en el proyecto FAB
        url = f"{conf['url']}/rest/api/3/search"
        query = {'jql': f'project="{conf["project_key"]}"', 'fields': 'summary,status'}
        
        res = requests.get(url, params=query, auth=auth, timeout=5)
        if res.status_code == 200:
            # Crea diccionario { "ID_Pedido": "Estado_Jira" }
            return {iss['fields']['summary'].replace("MAG-","").strip(): iss['fields']['status']['name'] for iss in res.json().get('issues', [])}
    except Exception as e:
        return {} # Si falla Jira, la app sigue funcionando sin estados
    return {}

# --- 3. EJECUCIÓN ---

df, ws = cargar_todo()
jira_status = consultar_jira()

if not df.empty:
    st.title("🚀 Sistema Magallan Integrado")
    
    # MÉTRICAS SUPERIORES
    m1, m2, m3, m4 = st.columns(4)
    total_vta = df['Monto_Total'].sum()
    total_cob = df['Anticipo'].sum()
    total_pen = df['Saldo'].sum()
    
    m1.metric("VENTAS TOTALES", f"${total_vta:,.0f}")
    m2.metric("COBRADO", f"${total_cob:,.0f}", delta=f"{(total_cob/total_vta)*100:.1f}%")
    m3.metric("PENDIENTE", f"${total_pen:,.0f}", delta_color="inverse")
    m4.metric("TICKETS TALLER", len(jira_status))

    st.divider()

    col_izq, col_der = st.columns([1, 2])

    # FORMULARIO DE CARGA (Funcionalidad anterior)
    with col_izq:
        st.subheader("📝 Nuevo Registro")
        with st.form("nueva_vta", clear_on_submit=True):
            f_nro = st.text_input("MAG# (Número de pedido)")
            f_cli = st.text_input("Nombre del Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            f_corp = st.checkbox("¿Es Cuenta Corporativa?")
            f_tot = st.number_input("Monto Total ($)", step=100.0)
            f_ant = st.number_input("Anticipo Cobrado ($)", step=100.0)
            f_fec = st.date_input("Fecha", datetime.now())
            
            if st.form_submit_button("GUARDAR EN PLANILLA"):
                nueva_fila = [
                    f_fec.strftime("%Y-%m-%d"), f_nro, f_cli, f_tot, f_ant, 
                    f_ven, "No", f_fec.strftime("%Y-%m-%d"), "SI" if f_corp else "NO"
                ]
                ws.append_row(nueva_fila)
                st.success("¡Venta registrada!")
                st.rerun()

    # LISTADO VISUAL CON JIRA
    with col_der:
        st.subheader("📑 Cartera de Clientes y Producción")
        busqueda = st.text_input("🔍 Buscar por cliente o número...")
        
        df_ver = df[df.apply(lambda r: busqueda.lower() in str(r.values).lower(), axis=1)] if busqueda else df
        
        for i, fila in df_ver.sort_values(by='Fecha', ascending=False).iterrows():
            # Cruce con Jira
            ticket_id = str(fila['Nro_Ppto']).strip()
            estado_jira = jira_status.get(ticket_id, "Sin Ticket")
            
            es_corp = str(fila['Corporativa']).upper() == "SI"
            clase_monto = "monto-ok" if fila['Saldo'] <= 0 else "monto-deuda"
            
            st.markdown(f"""
                <div class="{'card-corp' if es_corp else 'card-vendedor'}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex: 2;">
                            <span style="font-size: 1.1rem; font-weight: bold;">MAG-{fila['Nro_Ppto']} | {fila['Cliente']}</span>
                            <span class="tag-jira">🛠 {estado_jira}</span><br>
                            <small>👤 {fila['Vendedor']} | 📅 {fila.get('Fecha', 'S/F')}</small>
                        </div>
                        <div style="flex: 1; text-align: right;">
                            <div style="font-size: 0.8rem; color: #64748b;">PENDIENTE</div>
                            <div class="{clase_monto}">${fila['Saldo']:,.0f}</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Edición de saldos (Funcionalidad anterior)
            with st.expander(f"Actualizar saldo de {fila['Cliente']}"):
                c1, c2, c3 = st.columns(3)
                n_tot = c1.number_input("Total", value=float(fila['Monto_Total']), key=f"t{i}")
                n_ant = c2.number_input("Cobrado", value=float(fila['Anticipo']), key=f"a{i}")
                if c3.button("Guardar", key=f"b{i}"):
                    ws.update_cell(i+2, 4, n_tot)
                    ws.update_cell(i+2, 5, n_ant)
                    st.rerun()

    st.divider()

    # ANÁLISIS (Funcionalidad anterior)
    st.subheader("📊 Análisis")
    g1, g2 = st.columns(2)
    with g1:
        fig1 = px.bar(df.groupby('Origen')['Monto_Total'].sum().reset_index(), 
                      x='Origen', y='Monto_Total', title="Ventas por Origen", color='Origen')
        st.plotly_chart(fig1, use_container_width=True)
    with g2:
        fig2 = px.pie(names=['Cobrado', 'Pendiente'], values=[total_cob, total_pen], 
                      title="Salud de Cobranza", hole=0.4, color_discrete_sequence=['#10B981', '#E11D48'])
        st.plotly_chart(fig2, use_container_width=True)

else:
    st.warning("No se encontraron datos en la pestaña 'Saldos_Simples'.")