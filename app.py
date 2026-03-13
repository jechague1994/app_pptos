import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Magallan Dashboard Pro", layout="wide", page_icon="📈")

# Definición de la paleta Magallan
COLORES_VENDEDORES = {
    "Jacqueline": "#FF69B4", # Rosa
    "Jonathan": "#3b82f6",   # Azul
    "Roberto": "#22c55e"     # Verde
}

st.markdown("""
<style>
    [data-testid="stMetric"] { background: white; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .card-vendedor { background: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #3b82f6; box-shadow: 0 2px 5px rgba(0,0,0,0.08); }
    .card-corp { background: #1e293b; color: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #6366f1; }
    .monto-alerta { color: #e11d48; font-weight: 800; font-size: 1.2rem; }
    .monto-corp { color: #818cf8; font-weight: 800; font-size: 1.2rem; }
    .tag-joven { background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: bold; margin-left: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
@st.cache_resource(ttl=30)
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
        
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha_Aprobacion'] = pd.to_datetime(df['Fecha_Aprobacion'], errors='coerce')
        df['Fecha_Creacion'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce')
        df['Dias_Cierre'] = (df['Fecha_Aprobacion'] - df['Fecha_Creacion']).dt.days
        return df, ws
    except:
        return pd.DataFrame(), None

def fmt(n): return f"$ {n:,.0f}".replace(",", ".")

# --- 3. DASHBOARD ---
df, ws = cargar_datos()

if not df.empty:
    st.sidebar.header("🔍 Filtros")
    vendedores_lista = sorted([v for v in df['Vendedor'].unique() if v and v != "Distribuidor"])
    v_sel = st.sidebar.selectbox("Vendedor", ["Todos"] + vendedores_lista)
    
    df_f = df.copy()
    if v_sel != "Todos":
        df_f = df_f[df_f['Vendedor'] == v_sel]

    st.title("📊 Magallan Intelligence Pro")

    # MÉTRICAS
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS TOTALES", fmt(df_f['Monto_Total'].sum()))
    m2.metric("RECAUDADO", fmt(df_f['Anticipo'].sum()))
    m3.metric("DEUDA TOTAL", fmt(df_f['Saldo'].sum()), delta_color="inverse")
    avg_dias = df_f['Dias_Cierre'].mean()
    m4.metric("VELOCIDAD CIERRE", f"{avg_dias:.1f} días" if not pd.isna(avg_dias) else "0 días")

    st.divider()

    # --- GRÁFICOS CON COLORES FIJOS ---
    g1, g2, g3 = st.columns(3)
    
    with g1:
        # Dona: Participación de Ventas
        fig_vendedores = px.pie(df_f, values='Monto_Total', names='Vendedor', 
                                title="Ventas por Vendedor (%)",
                                hole=0.5, 
                                color='Vendedor',
                                color_discrete_map=COLORES_VENDEDORES)
        fig_vendedores.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_vendedores, use_container_width=True)
        
    with g2:
        # Torta: Estado de Facturación (Colores semánticos)
        fig_facturacion = px.pie(df_f, values='Monto_Total', names='Facturado', 
                                 title="Estado de Facturación",
                                 color='Facturado',
                                 color_discrete_map={"Facturado": "#2ecc71", "No Facturado": "#e74c3c"})
        fig_facturacion.update_traces(textinfo='percent+value')
        st.plotly_chart(fig_facturacion, use_container_width=True)
        
    with g3:
        # Ranking de Cobranza con colores fijos
        df_rank = df_f.groupby('Vendedor')['Anticipo'].sum().reset_index().sort_values('Anticipo', ascending=True)
        fig_rank = px.bar(df_rank, y='Vendedor', x='Anticipo', orientation='h', 
                          title="Ranking de Recaudación ($)",
                          color='Vendedor',
                          color_discrete_map=COLORES_VENDEDORES)
        st.plotly_chart(fig_rank, use_container_width=True)

    st.divider()

    # --- OPERATIVA ---
    col_l, col_r = st.columns([1.7, 1.3])

    with col_l:
        st.subheader("📑 Cartera de Clientes")
        busc = st.text_input("🔍 Buscar cliente...")
        df_v = df_f[df_f.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df_f
        
        for i, r in df_v.sort_values(by='Fecha_Aprobacion', ascending=False).iterrows():
            es_corp = str(r.get('Corporativa','')).upper() == "SI"
            clase = "card-corp" if es_corp else "card-vendedor"
            monto_clase = "monto-corp" if es_corp else "monto-alerta"
            dias = r['Dias_Cierre']
            tag_joven = f'<span class="tag-joven">⚡ CIERRE: {dias}d</span>' if (not pd.isna(dias) and dias <= 3) else ""
            
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <b>{r['Cliente']}</b> {tag_joven}<br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']} | {r['Facturado']}</small>
                        </div>
                        <div style="text-align:right;">
                            <span class="{monto_clase}">{fmt(r['Saldo'])}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander(f"Actualizar Cobro"):
                nv = st.number_input(f"Total ya cobrado (Actual: {fmt(r['Anticipo'])})", value=float(r['Anticipo']), step=1000.0, key=f"e_{i}")
                if st.button("Guardar", key=f"b_{i}"):
                    ws.update_cell(i+2, 5, nv)
                    st.success("¡Hecho!"); st.rerun()

    with col_r:
        st.subheader("📝 Registrar Venta")
        with st.form("alta_vta", clear_on_submit=True):
            f_crea = st.date_input("Fecha Creación Ppto", datetime.now())
            f_ppto = st.text_input("Nro Presupuesto")
            f_cli = st.text_input("Nombre Cliente")
            f_ven = st.selectbox("Vendedor", ["Jacqueline", "Jonathan", "Roberto"])
            f_fac = st.selectbox("Estado Factura", ["Facturado", "No Facturado"])
            f_tot = st.number_input("Monto Total $", min_value=0.0, step=1000.0)
            f_ant = st.number_input("Anticipo Inicial $", min_value=0.0, step=1000.0)
            f_corp = st.checkbox("¿Es Cuenta Corporativa?")
            
            if st.form_submit_button("REGISTRAR"):
                f_apro = datetime.now().strftime("%Y-%m-%d %H:%M")
                ws.append_row([f_crea.strftime("%Y-%m-%d"), f_ppto, f_cli, f_tot, f_ant, f_ven, f_fac, f_apro, "SI" if f_corp else "NO"])
                st.balloons(); st.rerun()
else:
    st.warning("Sin datos. Revisa los encabezados de tu Excel.")