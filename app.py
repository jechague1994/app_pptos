[14:46, 13/3/2026] Jonathan: import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Magallan Dashboard Pro", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .stMetric { background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
    .card-vendedor { background: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #3b82f6; box-shadow: 0 2px 5px rgba(0,0,0,0.08); }
    .card-corp { background: #f8fafc; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #1e293b; border: 1…
[14:50, 13/3/2026] Jonathan: import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Magallan Dashboard Pro", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .stMetric { background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
    .card-vendedor { background: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #3b82f6; box-shadow: 0 2px 5px rgba(0,0,0,0.08); }
    .card-corp { background: #f8fafc; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #1e293b; border: 1px solid #e2e8f0; }
    .monto-alerta { color: #e11d48; font-weight: 800; font-size: 1.2rem; }
    .saldo-info { font-size: 0.85rem; color: #64748b; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
@st.cache_resource(ttl=60)
def conectar_gs():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except: return None

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
        return df, ws
    except: return pd.DataFrame(), None

def fmt_money(valor):
    return f"$ {valor:,.0f}".replace(",", ".")

# --- 3. LÓGICA DE FILTROS Y SALDOS ---
df, ws = cargar_datos()

if not df.empty:
    # --- BARRA LATERAL ---
    st.sidebar.header("🔍 Filtros de Gestión")
    lista_vendedores = ["Todos"] + sorted([v for v in df['Vendedor'].unique() if v and v != "Distribuidor"])
    vendedor_sel = st.sidebar.selectbox("Vendedor Responsable", lista_vendedores)
    
    # Rango de fechas
    fecha_min_data = df['Fecha'].min().date() if not df['Fecha'].isnull().all() else datetime.now().date()
    rango = st.sidebar.date_input("Periodo seleccionado", [fecha_min_data, datetime.now().date()])

    # --- CÁLCULO DE SALDOS (JOVEN VS VIEJO) ---
    if len(rango) == 2:
        inicio, fin = rango
        # Saldo Viejo: Ventas antes del inicio del rango
        df_viejo = df[df['Fecha'].dt.date < inicio]
        saldo_viejo = df_viejo['Saldo'].sum()
        
        # Filtro principal para el dashboard (Saldo Joven)
        df_f = df[(df['Fecha'].dt.date >= inicio) & (df['Fecha'].dt.date <= fin)]
        if vendedor_sel != "Todos":
            df_f = df_f[df_f['Vendedor'] == vendedor_sel]
            df_viejo_vend = df_viejo[df_viejo['Vendedor'] == vendedor_sel]
            saldo_viejo = df_viejo_vend['Saldo'].sum()
            
        saldo_joven = df_f['Saldo'].sum()
    else:
        df_f = df
        saldo_joven = df['Saldo'].sum()
        saldo_viejo = 0

    st.title("📊 Panel Magallan Intelligence")

    # --- MÉTRICAS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VENTAS DEL PERIODO", fmt_money(df_f['Monto_Total'].sum()))
    c2.metric("COBRADO (PERIODO)", fmt_money(df_f['Anticipo'].sum()))
    c3.metric("SALDO JOVEN", fmt_money(saldo_joven), help="Deuda de las ventas dentro del rango de fechas")
    c4.metric("SALDO VIEJO", fmt_money(saldo_viejo), help="Deuda acumulada de ventas anteriores al rango")

    st.divider()

    # --- GRÁFICOS ---
    g1, g2, g3 = st.columns(3)
    with g1:
        fig_p = px.pie(df_f, values='Monto_Total', names='Vendedor', title="Cuota de Ventas", hole=0.4)
        st.plotly_chart(fig_p, use_container_width=True)
    with g2:
        df_fac = df_f.groupby('Facturado')['Monto_Total'].sum().reset_index()
        fig_b = px.bar(df_fac, x='Facturado', y='Monto_Total', color='Facturado', 
                       title="Facturado vs No Facturado",
                       color_discrete_map={"Facturado": "#00CC96", "No Facturado": "#EF553B"})
        st.plotly_chart(fig_b, use_container_width=True)
    with g3:
        df_t = df_f.dropna(subset=['Fecha']).sort_values('Fecha')
        df_t['Mes'] = df_t['Fecha'].dt.strftime('%b %y')
        df_res = df_t.groupby('Mes')['Monto_Total'].sum().reset_index()
        fig_a = px.area(df_res, x='Mes', y='Monto_Total', title="Evolución de Ventas", markers=True)
        st.plotly_chart(fig_a, use_container_width=True)

    st.divider()

    # --- LISTADO Y REGISTRO ---
    col_l, col_r = st.columns([1.8, 1.2])

    with col_l:
        st.subheader("📑 Cartera de Clientes")
        busc = st.text_input("🔍 Buscar cliente o ppto...")
        df_v = df_f[df_f.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df_f
        
        for i, r in df_v.sort_values(by='Fecha', ascending=False).iterrows():
            clase = "card-corp" if str(r.get('Corporativa','')).upper() == "SI" else "card-vendedor"
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <b>{r['Cliente']}</b><br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']} | {r['Facturado']}</small>
                        </div>
                        <div style="text-align:right;">
                            <span class="monto-alerta">{fmt_money(r['Saldo'])}</span><br>
                            <span class="saldo-info">{"JOVEN" if r['Fecha'].date() >= inicio else "VIEJO"}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar Pago"):
                nv = st.number_input(f"Total cobrado (Actual: {fmt_money(r['Anticipo'])})", value=float(r['Anticipo']), step=1000.0, key=f"p_{i}")
                if st.button("Guardar", key=f"b_{i}"):
                    ws.update_cell(i+2, 5, nv)
                    st.rerun()

    with col_r:
        st.subheader("📝 Nueva Venta")
        with st.form("alta", clear_on_submit=True):
            f_ppto = st.text_input("Nro Presupuesto")
            f_cli = st.text_input("Nombre Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto"])
            f_fac = st.selectbox("Estado Factura", ["Facturado", "No Facturado"])
            f_tot = st.number_input("Monto Total $", min_value=0.0, step=1000.0)
            f_ant = st.number_input("Anticipo $", min_value=0.0, step=1000.0)
            f_corp = st.checkbox("Cuenta Corporativa")
            if st.form_submit_button("REGISTRAR"):
                hoy = datetime.now().strftime("%Y-%m-%d")
                ws.append_row([hoy, f_ppto, f_cli, f_tot, f_ant, f_ven, f_fac, hoy, "SI" if f_corp else "NO"])
                st.rerun()
else:
    st.info("Conectado. Esperando datos...")