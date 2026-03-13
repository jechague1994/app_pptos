import streamlit as st
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
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource(ttl=60)
def conectar_gs():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def cargar_datos():
    gc = conectar_gs()
    if not gc: return pd.DataFrame(), None
    try:
        sh = gc.open("Gestion_Magallan")
        ws = sh.worksheet("Saldos_Simples")
        df = pd.DataFrame(ws.get_all_records())
        # Asegurar conversión de fechas
        df['Fecha_Aprobacion'] = pd.to_datetime(df['Fecha_Aprobacion'], errors='coerce')
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        return df, ws
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
        return pd.DataFrame(), None

# --- 3. PROCESAMIENTO ---
df, ws = cargar_datos()

if not df.empty:
    # --- BARRA LATERAL (FILTROS) ---
    st.sidebar.header("🔍 Filtros de Gestión")
    lista_vendedores = ["Todos"] + sorted([v for v in df['Vendedor'].unique() if v and v != "Distribuidor"])
    vendedor_sel = st.sidebar.selectbox("Vendedor Responsable", lista_vendedores)
    
    # El dashboard ahora se rige por la Fecha de Aprobación
    f_min = df['Fecha_Aprobacion'].min().date() if not df['Fecha_Aprobacion'].isnull().all() else datetime.now().date()
    rango_fecha = st.sidebar.date_input("Filtrar por Fecha de Aprobación", [f_min, datetime.now().date()])

    df_f = df.copy()
    if vendedor_sel != "Todos":
        df_f = df_f[df_f['Vendedor'] == vendedor_sel]
    if len(rango_fecha) == 2:
        df_f = df_f[(df_f['Fecha_Aprobacion'].dt.date >= rango_fecha[0]) & (df_f['Fecha_Aprobacion'].dt.date <= rango_fecha[1])]

    st.title("📊 Panel Magallan Intelligence")

    # --- MÉTRICAS CON SEPARADOR DE MILES ---
    m1, m2, m3, m4 = st.columns(4)
    def fmt(n): return f"$ {n:,.0f}".replace(",", ".")
    
    m1.metric("VENTAS TOTALES", fmt(df_f['Monto_Total'].sum()))
    m2.metric("COBRADO", fmt(df_f['Anticipo'].sum()))
    m3.metric("DEUDA TOTAL", fmt(df_f['Saldo'].sum()), delta_color="inverse")
    m4.metric("OPERACIONES", len(df_f))

    st.divider()

    # --- GRÁFICOS ---
    g1, g2, g3 = st.columns(3)
    with g1:
        fig_p = px.pie(df_f, values='Monto_Total', names='Vendedor', title="Ventas por Vendedor", hole=0.4)
        st.plotly_chart(fig_p, use_container_width=True)
    with g2:
        df_fac = df_f.groupby('Facturado')['Monto_Total'].sum().reset_index()
        fig_b = px.bar(df_fac, x='Facturado', y='Monto_Total', color='Facturado', 
                       title="Facturado vs No Facturado",
                       color_discrete_map={"Facturado": "#00CC96", "No Facturado": "#EF553B"})
        st.plotly_chart(fig_b, use_container_width=True)
    with g3:
        df_t = df_f.dropna(subset=['Fecha_Aprobacion']).sort_values('Fecha_Aprobacion')
        df_t['Mes'] = df_t['Fecha_Aprobacion'].dt.strftime('%b %y')
        df_res = df_t.groupby('Mes')['Monto_Total'].sum().reset_index()
        fig_a = px.area(df_res, x='Mes', y='Monto_Total', title="Tendencia de Aprobaciones", markers=True)
        st.plotly_chart(fig_a, use_container_width=True)

    st.divider()

    # --- LISTADO Y FORMULARIO ---
    col_l, col_r = st.columns([1.8, 1.2])

    with col_l:
        st.subheader("📑 Cartera de Clientes")
        busc = st.text_input("🔍 Buscar cliente o presupuesto...")
        df_v = df_f[df_f.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df_f
        
        for i, r in df_v.sort_values(by='Fecha_Aprobacion', ascending=False).iterrows():
            clase = "card-corp" if str(r.get('Corporativa','')).upper() == "SI" else "card-vendedor"
            f_crea = r['Fecha_Creacion'] if 'Fecha_Creacion' in r else "N/A"
            
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <b>{r['Cliente']}</b><br>
                            <small>Ppto: {r['Nro_Ppto']} | Creado: {f_crea} | {r['Vendedor']}</small><br>
                            <small style="color: #64748b;">Estado: {r['Facturado']}</small>
                        </div>
                        <div style="text-align:right;">
                            <span class="monto-alerta">{fmt(r['Saldo'])}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander(f"Actualizar cobro"):
                nv = st.number_input(f"Total cobrado (Actual: {fmt(r['Anticipo'])})", value=float(r['Anticipo']), step=1000.0, key=f"pay_{i}")
                if st.button("Guardar Cambios", key=f"btn_{i}"):
                    ws.update_cell(i+2, 5, nv)
                    st.success("¡Venta actualizada!")
                    st.rerun()

    with col_r:
        st.subheader("📝 Nueva Venta")
        with st.form("alta_vta", clear_on_submit=True):
            f_creacion = st.date_input("Fecha de Creación del Ppto", datetime.now())
            f_ppto = st.text_input("Nro Presupuesto")
            f_cli = st.text_input("Nombre Cliente")
            f_ven = st.selectbox("Vendedor Responsable", ["Jonathan", "Jacqueline", "Roberto"])
            f_fac = st.selectbox("Estado de Factura", ["Facturado", "No Facturado"])
            f_tot = st.number_input("Monto Total $", min_value=0.0, step=1000.0)
            f_ant = st.number_input("Anticipo $", min_value=0.0, step=1000.0)
            f_corp = st.checkbox("¿Es Cuenta Corporativa?")
            
            if st.form_submit_button("REGISTRAR EN EL SISTEMA"):
                f_aprobacion = datetime.now().strftime("%Y-%m-%d %H:%M") # AUTOMÁTICA
                # Columnas sugeridas: Fecha_Crea, Nro_Ppto, Cliente, Monto, Anticipo, Vendedor, Factura, Fecha_Apro, Corp
                ws.append_row([
                    f_creacion.strftime("%Y-%m-%d"), 
                    f_ppto, 
                    f_cli, 
                    f_tot, 
                    f_ant, 
                    f_ven, 
                    f_fac, 
                    f_aprobacion, 
                    "SI" if f_corp else "NO"
                ])
                st.balloons()
                st.rerun()
else:
    st.info("Conectado. Esperando datos...")