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

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .metric-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-top: 4px solid #3b82f6; text-align: center; }
    .card-vendedor { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .card-corp { background: #f1f5f9; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #1e293b; border: 1px solid #cbd5e1; }
    .status-badge { background: #e2e8f0; color: #475569; padding: 3px 10px; border-radius: 15px; font-size: 0.75rem; font-weight: bold; border: 1px solid #94a3b8; }
    .monto-alerta { color: #e11d48; font-weight: 800; font-size: 1.2rem; }
    .monto-ok { color: #10b981; font-weight: 800; font-size: 1.2rem; }
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
        
        # Procesamiento
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        
        # Lógica de Saldos Jóvenes y Viejos
        hoy = datetime.now()
        df['Antiguedad'] = (hoy - df['Fecha']).dt.days
        df['Estado_Deuda'] = df.apply(
            lambda r: 'Viejo' if r['Antiguedad'] > 30 and r['Saldo'] > 0 else ('Joven' if r['Saldo'] > 0 else 'Pagado'), 
            axis=1
        )
        # Para gráfico mensual
        df['Mes_Año'] = df['Fecha'].dt.strftime('%Y-%m')
        
        return df, ws
    except Exception as e:
        st.error(f"Error Sheets: {e}")
        return pd.DataFrame(), None

def consultar_jira():
    try:
        conf = st.secrets["jira"]
        url = f"{conf['url']}/rest/api/3/search"
        auth = HTTPBasicAuth(conf["user"], conf["token"])
        query = {'jql': f'project="{conf["project_key"]}"', 'fields': 'summary,status'}
        res = requests.get(url, params=query, auth=auth, timeout=7)
        if res.status_code == 200:
            issues = res.json().get('issues', [])
            mapping = {}
            for iss in issues:
                summary = str(iss['fields']['summary']).upper().replace("MAG-", "").strip()
                mapping[summary] = iss['fields']['status']['name']
            return mapping
    except:
        return {}
    return {}

# --- 3. LÓGICA DE INTERFAZ ---

df, ws = cargar_datos()
dict_jira = consultar_jira()

if not df.empty:
    st.title("🚀 Sistema Magallan Integrado")
    
    # MÉTRICAS GENERALES
    t1, t2, t3, t4 = st.columns(4)
    total_vta = df['Monto_Total'].sum()
    total_cob = df['Anticipo'].sum()
    total_pen = df['Saldo'].sum()
    
    t1.metric("VENTAS TOTALES", f"${total_vta:,.0f}")
    t2.metric("COBRADO TOTAL", f"${total_cob:,.0f}", f"{(total_cob/total_vta)*100:.1f}%")
    t3.metric("PENDIENTE COBRO", f"${total_pen:,.0f}", delta_color="inverse")
    t4.metric("PEDIDOS EN TALLER", len(dict_jira))

    # --- ANÁLISIS DE ENVEJECIMIENTO ---
    st.markdown("### ⏳ Envejecimiento de Deuda")
    c_jov, c_vie, c_pag = st.columns(3)
    val_joven = df[df['Estado_Deuda'] == 'Joven']['Saldo'].sum()
    val_viejo = df[df['Estado_Deuda'] == 'Viejo']['Saldo'].sum()
    
    c_jov.markdown(f"<div class='metric-card'><b>Saldos Jóvenes (0-30 días)</b><br><span style='color:#3b82f6; font-size:1.8rem; font-weight:bold;'>${val_joven:,.0f}</span></div>", unsafe_allow_html=True)
    c_vie.markdown(f"<div class='metric-card' style='border-top-color:#e11d48;'><b>Saldos Viejos (>30 días)</b><br><span style='color:#e11d48; font-size:1.8rem; font-weight:bold;'>${val_viejo:,.0f}</span></div>", unsafe_allow_html=True)
    c_pag.markdown(f"<div class='metric-card' style='border-top-color:#10b981;'><b>Cobranza Efectiva</b><br><span style='color:#10b981; font-size:1.8rem; font-weight:bold;'>${total_cob:,.0f}</span></div>", unsafe_allow_html=True)

    st.divider()

    # --- CUERPO PRINCIPAL ---
    col_reg, col_list = st.columns([1.2, 2])

    with col_reg:
        st.subheader("📝 Nuevo Registro")
        with st.form("form_alta", clear_on_submit=True):
            f_nro = st.text_input("MAG# / Pedido")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            f_corp = st.checkbox("¿Es Cuenta Corporativa?")
            f_tot = st.number_input("Monto Total ($)", step=1.0)
            f_ant = st.number_input("Anticipo Recibido ($)", step=1.0)
            f_fec = st.date_input("Fecha Venta", datetime.now())
            if st.form_submit_button("REGISTRAR VENTA"):
                nueva = [f_fec.strftime("%Y-%m-%d"), f_nro, f_cli, f_tot, f_ant, f_ven, "No", f_fec.strftime("%Y-%m-%d"), "SI" if f_corp else "NO"]
                ws.append_row(nueva)
                st.success("¡Registro Exitoso!")
                st.rerun()

    with col_list:
        st.subheader("📑 Cartera de Clientes")
        busc = st.text_input("🔍 Buscar por cliente o número...")
        df_f = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        for i, fila in df_f.sort_values(by='Fecha', ascending=False).iterrows():
            nro_limpio = str(fila['Nro_Ppto']).strip()
            est_jira = dict_jira.get(nro_limpio, dict_jira.get(f"MAG-{nro_limpio}", "Sin Ticket"))
            es_corp = str(fila['Corporativa']).upper() == "SI"
            clase_monto = "monto-ok" if fila['Saldo'] <= 0 else "monto-alerta"
            icon_deuda = "🔴" if fila['Estado_Deuda'] == 'Viejo' else "🔵"
            
            st.markdown(f"""
                <div class="{'card-corp' if es_corp else 'card-vendedor'}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <span style="font-size:1.1rem; font-weight:bold;">{fila['Cliente']}</span> 
                            <span class="status-badge">🛠 {est_jira}</span><br>
                            <small>{icon_deuda} MAG-{nro_limpio} | {fila['Vendedor']} | {fila['Fecha'].strftime('%d/%m/%Y')}</small>
                        </div>
                        <div style="text-align:right;">
                            <small>PENDIENTE</small><br>
                            <span class="{clase_monto}">${fila['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar Cobro"):
                nuevo_ant = st.number_input("Total cobrado", value=float(fila['Anticipo']), key=f"inp_{i}")
                if st.button("Guardar Pago", key=f"btn_{i}"):
                    ws.update_cell(i+2, 5, nuevo_ant)
                    st.rerun()

    # --- 4. SECCIÓN DE ESTADÍSTICAS ---
    st.divider()
    st.subheader("📊 Análisis de Crecimiento y Rendimiento")
    
    # Gráfico de Ventas Mensuales (Agregado solicitado)
    df_mensual = df.groupby('Mes_Año')['Monto_Total'].sum().reset_index()
    fig_mes = px.line(df_mensual, x='Mes_Año', y='Monto_Total', title="Evolución de Ventas Mensuales", 
                      markers=True, line_shape="spline", color_discrete_sequence=['#3b82f6'])
    st.plotly_chart(fig_mes, use_container_width=True)

    g1, g2 = st.columns(2)
    with g1:
        fig1 = px.pie(df[df['Saldo']>0], values='Saldo', names='Estado_Deuda', 
                     title="Composición de la Deuda", color_discrete_map={'Viejo':'#e11d48', 'Joven':'#3b82f6'})
        st.plotly_chart(fig1, use_container_width=True)
    with g2:
        fig2 = px.bar(df.groupby('Vendedor')['Monto_Total'].sum().reset_index(), 
                     x='Vendedor', y='Monto_Total', title="Ventas Totales por Vendedor")
        st.plotly_chart(fig2, use_container_width=True)

else:
    st.warning("Sin datos en la hoja 'Saldos_Simples'.")