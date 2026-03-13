import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth

# --- 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(page_title="Magallan Sistema Integrado", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    /* Estilo General */
    .stApp { background-color: #F1F5F9; }
    
    /* Tarjetas de Clientes */
    .card-vendedor { 
        background: white; 
        border-radius: 10px; 
        padding: 15px; 
        margin-bottom: 12px; 
        border-left: 6px solid #3B82F6; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .card-corp { 
        background: #F8FAFC; 
        border-radius: 10px; 
        padding: 15px; 
        margin-bottom: 12px; 
        border-left: 6px solid #1E293B; 
        border: 1px solid #CBD5E1;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Indicadores de Montos */
    .monto-deuda { color: #E11D48; font-size: 1.2rem; font-weight: 800; text-align: right; }
    .monto-ok { color: #10B981; font-size: 1.2rem; font-weight: 800; text-align: right; }
    
    /* Etiquetas de Jira */
    .tag-jira { 
        background: #E2E8F0; 
        color: #475569; 
        padding: 2px 8px; 
        border-radius: 5px; 
        font-size: 0.75rem; 
        font-weight: bold;
        border: 1px solid #94A3B8;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCIONES DE CONEXIÓN ---

@st.cache_resource(ttl=60)
def conectar_google_sheets():
    try:
        # Usamos la estructura de secretos que configuramos
        info = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(
            info, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error de credenciales Google: {e}")
        return None

def cargar_datos():
    gc = conectar_google_sheets()
    if not gc: return pd.DataFrame(), None
    try:
        # Abrir el archivo y la pestaña específica
        sh = gc.open("Gestion_Magallan")
        ws = sh.worksheet("Saldos_Simples")
        df = pd.DataFrame(ws.get_all_records())
        
        # Procesamiento de datos numéricos
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        
        # Etiqueta de origen para gráficos
        df['Origen'] = df.apply(lambda r: "CORPORATIVO" if str(r['Corporativa']).upper() == "SI" else r['Vendedor'], axis=1)
        
        return df, ws
    except Exception as e:
        st.error(f"Error al leer la planilla: {e}")
        return pd.DataFrame(), None

def consultar_jira():
    try:
        conf = st.secrets["jira"]
        auth = HTTPBasicAuth(conf["user"], conf["token"])
        url = f"{conf['url']}/rest/api/3/search"
        query = {'jql': f'project="{conf["project_key"]}"', 'fields': 'summary,status'}
        
        res = requests.get(url, params=query, auth=auth, timeout=5)
        if res.status_code == 200:
            # Crea un diccionario { "NumeroMAG": "EstadoJira" }
            return {iss['fields']['summary'].replace("MAG-","").strip(): iss['fields']['status']['name'] for iss in res.json().get('issues', [])}
    except:
        return {}
    return {}

# --- 3. LÓGICA DE LA APP ---

df, ws = cargar_datos()
jira_status = consultar_jira()

if not df.empty:
    st.title("🚀 Panel de Control Magallan")
    
    # --- MÉTRICAS SUPERIORES ---
    m1, m2, m3, m4 = st.columns(4)
    total_vta = df['Monto_Total'].sum()
    total_cob = df['Anticipo'].sum()
    total_pen = df['Saldo'].sum()
    
    m1.metric("VENTAS TOTALES", f"${total_vta:,.0f}")
    m2.metric("COBRADO", f"${total_cob:,.0f}", delta=f"{(total_cob/total_vta)*100:.1f}%", delta_color="normal")
    m3.metric("PENDIENTE", f"${total_pen:,.0f}", delta=f"-${total_pen:,.0f}", delta_color="inverse")
    m4.metric("PROYECTOS FAB", len(jira_status))

    st.divider()

    # --- CUERPO PRINCIPAL ---
    col_form, col_lista = st.columns([1, 2.5])

    # FORMULARIO DE INGRESO (Izquierda)
    with col_form:
        st.subheader("📝 Nuevo Registro")
        with st.form("registro_venta", clear_on_submit=True):
            f_nro = st.text_input("Número MAG#")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Otro"])
            f_corp = st.checkbox("¿Es Cuenta Corporativa?")
            f_tot = st.number_input("Monto Total ($)", min_value=0.0, step=1000.0)
            f_ant = st.number_input("Anticipo / Cobrado ($)", min_value=0.0, step=1000.0)
            f_fec = st.date_input("Fecha de Venta", datetime.now())
            
            if st.form_submit_button("REGISTRAR VENTA"):
                nueva_fila = [
                    f_fec.strftime("%Y-%m-%d"), 
                    f_nro, 
                    f_cli, 
                    f_tot, 
                    f_ant, 
                    f_ven, 
                    "No", # Facturado
                    datetime.now().strftime("%Y-%m-%d"), # Fecha Conf
                    "SI" if f_corp else "NO"
                ]
                ws.append_row(nueva_fila)
                st.success("¡Venta guardada!")
                st.rerun()

    # LISTADO Y GESTIÓN (Derecha)
    with col_lista:
        st.subheader("📑 Gestión de Cartera y Producción")
        busqueda = st.text_input("🔍 Buscar por cliente o número de pedido...")
        
        # Filtrado
        df_ver = df[df.apply(lambda r: busqueda.lower() in str(r.values).lower(), axis=1)] if busqueda else df
        
        for i, fila in df_ver.sort_values(by='Fecha', ascending=False).iterrows():
            # Obtener estado de Jira
            ticket = str(fila['Nro_Ppto']).strip()
            estado_taller = jira_status.get(ticket, "No iniciado")
            
            # Determinar estilo
            es_corp = str(fila['Corporativa']).upper() == "SI"
            estilo_card = "card-corp" if es_corp else "card-vendedor"
            clase_monto = "monto-ok" if fila['Saldo'] <= 0 else "monto-deuda"
            texto_saldo = "PAGADO" if fila['Saldo'] <= 0 else f"${fila['Saldo']:,.0f}"
            
            # Renderizado de Tarjeta
            st.markdown(f"""
                <div class="{estilo_card}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex: 2;">
                            <span style="font-size: 1.1rem; font-weight: bold;">MAG-{fila['Nro_Ppto']} | {fila['Cliente']}</span>
                            <span class="tag-jira">🛠 {estado_taller}</span><br>
                            <small>👤 {fila['Vendedor']} | 📅 {fila['Fecha'].strftime('%d/%m/%Y') if not pd.isnull(fila['Fecha']) else 'S/F'}</small>
                        </div>
                        <div style="flex: 1; text-align: right;">
                            <div style="font-size: 0.8rem; color: #64748b;">PENDIENTE</div>
                            <div class="{clase_monto}">{texto_saldo}</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Botón de edición rápida
            with st.expander(f"Editar saldos de {fila['Cliente']}"):
                c1, c2, c3 = st.columns(3)
                nuevo_tot = c1.number_input("Monto Total", value=float(fila['Monto_Total']), key=f"tot_{i}")
                nuevo_ant = c2.number_input("Anticipo", value=float(fila['Anticipo']), key=f"ant_{i}")
                if c3.button("Actualizar", key=f"btn_{i}"):
                    # En gspread, las filas son index+2 (cabecera + base 0)
                    ws.update_cell(i+2, 4, nuevo_tot)
                    ws.update_cell(i+2, 5, nuevo_ant)
                    st.success("Actualizado")
                    st.rerun()

    st.divider()

    # --- 4. GRÁFICOS DE RENDIMIENTO ---
    st.subheader("📊 Análisis de Rendimiento")
    g1, g2 = st.columns(2)
    
    with g1:
        # Ventas por Vendedor/Corp
        fig_ven = px.bar(df.groupby('Origen')['Monto_Total'].sum().reset_index(), 
                         x='Origen', y='Monto_Total', title="Ventas Totales por Origen",
                         color='Origen', color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_ven, use_container_width=True)
        
    with g2:
        # Estado de Cobranza General
        cobranza = pd.DataFrame({
            'Estado': ['Cobrado', 'Pendiente'],
            'Monto': [total_cob, total_pen]
        })
        fig_pie = px.pie(cobranza, values='Monto', names='Estado', title="Salud Financiera (Total)",
                         color_discrete_sequence=['#10B981', '#E11D48'], hole=0.5)
        st.plotly_chart(fig_pie, use_container_width=True)

else:
    st.info("Esperando conexión con Google Sheets. Asegúrate de que el archivo 'Gestion_Magallan' exista y esté compartido.")