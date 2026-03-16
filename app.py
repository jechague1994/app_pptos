import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Rendimiento de Montos y Saldos", layout="wide", page_icon="📊")

META_VENTAS = 150000000  # 150 Millones
COLORES_VENDEDORES = {"Jacqueline": "#FFB6C1", "Jonathan": "#ADD8E6", "Roberto": "#98FB98", "Corporativo": "#CBD5E1"}

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: white !important; padding: 15px !important; border-radius: 10px !important; border: 1px solid #e2e8f0 !important; }
    .card-vendedor { background-color: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #3b82f6; box-shadow: 0 2px 5px rgba(0,0,0,0.08); }
    .card-corp { background-color: #1e293b; color: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #6366f1; }
    .monto-alerta { color: #e11d48; font-weight: 800; font-size: 1.2rem; }
    .sub-metrica { font-size: 0.9rem; color: #64748b; font-weight: 600; margin-bottom: 2px; }
    .ticket-promedio { font-size: 0.85rem; color: #059669; font-style: italic; }
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
        if 'Estado' not in df.columns: df['Estado'] = 'Pendiente'
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha_Creacion'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce')
        df['Días_Fabricación'] = (datetime.now() - df['Fecha_Creacion']).dt.days.fillna(0).astype(int)
        df['Es_Corp'] = (df['Corporativa'].astype(str).str.upper() == "SI") | (df['Vendedor'].astype(str).str.upper() == "CORPORATIVO")
        return df, ws
    except Exception as e:
        st.error(f"Error cargando Excel: {e}")
        return pd.DataFrame(), None

def fmt(n): return f"$ {n:,.0f}".replace(",", ".")

# --- 3. DASHBOARD ---
df, ws = cargar_datos()

if df is not None and not df.empty:
    st.sidebar.header("🔍 Configuración")
    ver_completados = st.sidebar.checkbox("Ver Historial (Completados)")
    
    df['Estado_Limpio'] = df['Estado'].apply(lambda x: 'Completado' if str(x).strip() == 'Completado' else 'Pendiente')
    estado_filtro = 'Completado' if ver_completados else 'Pendiente'
    df_base = df[df['Estado_Limpio'] == estado_filtro].copy()

    st.title("📈 Rendimiento de Montos y Saldos")

    # --- CÁLCULOS ---
    df_v = df_base[df_base['Es_Corp'] == False]
    df_c = df_base[df_base['Es_Corp'] == True]
    ventas_vendedores = df_v['Monto_Total'].sum()

    # --- PANEL DE META (NUEVO) ---
    porcentaje = min((ventas_vendedores / META_VENTAS), 1.0)
    fig_meta = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = ventas_vendedores,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Progreso Meta Equipo (150M)", 'font': {'size': 20}},
        delta = {'reference': META_VENTAS, 'increasing': {'color': "green"}},
        gauge = {
            'axis': {'range': [None, META_VENTAS], 'tickformat': '$,.0f'},
            'bar': {'color': "#3b82f6"},
            'steps': [
                {'range': [0, META_VENTAS*0.5], 'color': "#fee2e2"},
                {'range': [META_VENTAS*0.5, META_VENTAS*0.8], 'color': "#fef9c3"},
                {'range': [META_VENTAS*0.8, META_VENTAS], 'color': "#dcfce7"}],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': META_VENTAS}}))
    fig_meta.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig_meta, use_container_width=True)

    # --- SECCIÓN DE MÉTRICAS COMPARATIVAS ---
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("👥 Equipo Ventas")
        st.metric("Ventas Totales", fmt(ventas_vendedores))
        st.markdown(f"<p class='sub-metrica'>Saldo Pendiente: <span style='color:#e11d48'>{fmt(df_v['Saldo'].sum())}</span></p>", unsafe_allow_html=True)
        st.markdown(f"<p class='ticket-promedio'>Ticket Promedio: {fmt(df_v['Monto_Total'].mean() if not df_v.empty else 0)}</p>", unsafe_allow_html=True)

    with c2:
        st.subheader("🏢 Corporativos")
        st.metric("Ventas Totales", fmt(df_c['Monto_Total'].sum()))
        st.markdown(f"<p class='sub-metrica'>Saldo Pendiente: <span style='color:#6366f1'>{fmt(df_c['Saldo'].sum())}</span></p>", unsafe_allow_html=True)
        st.markdown(f"<p class='ticket-promedio'>Ticket Promedio: {fmt(df_c['Monto_Total'].mean() if not df_c.empty else 0)}</p>", unsafe_allow_html=True)

    with c3:
        st.subheader("🌍 Total General")
        st.metric("Ventas Globales", fmt(df_base['Monto_Total'].sum()))
        st.markdown(f"<p class='sub-metrica'>Saldo Global: <b>{fmt(df_base['Saldo'].sum())}</b></p>", unsafe_allow_html=True)
        st.markdown(f"<p class='ticket-promedio'>Restante para Meta: {fmt(max(0, META_VENTAS - ventas_vendedores))}</p>", unsafe_allow_html=True)

    st.divider()

    # --- ANÁLISIS POR VENDEDOR ---
    st.subheader("📊 Ticket Promedio por Vendedor")
    v_nombres = sorted(df_v['Vendedor'].unique())
    v_cols = st.columns(len(v_nombres)) if v_nombres else [st.container()]
    for idx, vend in enumerate(v_nombres):
        df_vend = df_v[df_v['Vendedor'] == vend]
        avg = df_vend['Monto_Total'].mean() if not df_vend.empty else 0
        with v_cols[idx]:
            st.markdown(f"""
            <div style="background:{COLORES_VENDEDORES.get(vend, '#f1f5f9')}; padding:10px; border-radius:10px; text-align:center; border: 1px solid #ddd;">
                <h4 style="margin:0;">{vend}</h4>
                <p style="margin:0; font-size:1.1rem; font-weight:bold;">{fmt(avg)}</p>
                <small>{len(df_vend)} ventas</small>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # --- GRÁFICOS Y LISTA (Igual que v33) ---
    g1, g2, g3 = st.columns(3)
    with g1: st.plotly_chart(px.pie(df_v, values='Monto_Total', names='Vendedor', title="Cuota Ventas Equipo", hole=0.5, color='Vendedor', color_discrete_map=COLORES_VENDEDORES), use_container_width=True)
    with g2: st.plotly_chart(px.pie(df_v, values='Monto_Total', names='Facturado', title="Facturación", color='Facturado', color_discrete_map={"Facturado": "#A7F3D0", "No Facturado": "#FCA5A5"}), use_container_width=True)
    with g3:
        df_rank = df_v.groupby('Vendedor')['Anticipo'].sum().reset_index()
        st.plotly_chart(px.bar(df_rank, y='Vendedor', x='Anticipo', orientation='h', title="Recaudación Equipo", color='Vendedor', color_discrete_map=COLORES_VENDEDORES), use_container_width=True)

    st.divider()

    col_l, col_r = st.columns([1.7, 1.3])
    with col_l:
        st.subheader("📑 Cartera Pendiente")
        busc = st.text_input("🔍 Buscar cliente...")
        df_display = df_base[df_base.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df_base
        for i, r in df_display.sort_values(by='Fecha_Creacion', ascending=False).iterrows():
            dias_f = int(r['Días_Fabricación'])
            clase = "card-corp" if r['Es_Corp'] else ("card-vendedor")
            st.markdown(f"""<div class="{clase}"><div style="display:flex; justify-content:space-between;"><div><b>{r['Cliente']}</b><br><small>{r['Nro_Ppto']} | {r['Vendedor']}</small></div>
                        <div style="text-align:right;"><small>{fmt(r['Monto_Total'])}</small><br><b>Saldo: {fmt(r['Saldo'])}</b></div></div></div>""", unsafe_allow_html=True)
            with st.expander(f"Editar {r['Cliente']}"):
                nt = st.number_input("Total:", value=float(r['Monto_Total']), key=f"t_{i}")
                np = st.number_input("Pago:", value=float(r['Anticipo']), key=f"p_{i}")
                if st.button("💾 Guardar", key=f"s_{i}"):
                    ws.update_cell(i+2, 4, nt); ws.update_cell(i+2, 5, np); st.rerun()
                if st.button("🏁 Completar", key=f"st_{i}"):
                    ws.update_cell(i+2, 10, "Completado"); st.rerun()

    with col_r:
        st.subheader("📝 Nuevo Registro")
        with st.form("alta"):
            f_ppto = st.text_input("Nro Ppto"); f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jacqueline", "Jonathan", "Roberto", "Corporativo"])
            f_tot = st.number_input("Monto Total", min_value=0.0); f_ant = st.number_input("Anticipo", min_value=0.0)
            f_corp = st.checkbox("¿Es Corporativa?")
            if st.form_submit_button("REGISTRAR"):
                ws.append_row([datetime.now().strftime("%Y-%m-%d"), f_ppto, f_cli, f_tot, f_ant, f_ven, "No Facturado", "", "SI" if f_corp else "NO", "Pendiente"])
                st.balloons(); st.rerun()