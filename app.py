import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Rendimiento de Montos y Saldos", layout="wide", page_icon="📊")

META_VENTAS = 150000000 
COLORES_VENDEDORES = {"Jacqueline": "#FFB6C1", "Jonathan": "#ADD8E6", "Roberto": "#98FB98", "Corporativo": "#CBD5E1"}

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: white !important; padding: 15px !important; border-radius: 10px !important; border: 1px solid #e2e8f0 !important; }
    .card-vendedor { background-color: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #3b82f6; box-shadow: 0 2px 5px rgba(0,0,0,0.08); }
    .card-corp { background-color: #1e293b; color: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #6366f1; }
    .monto-alerta { color: #e11d48; font-weight: 800; font-size: 1.2rem; }
    .sub-metrica { font-size: 0.9rem; color: #64748b; font-weight: 600; }
    .status-badge { font-size: 0.75rem; padding: 3px 8px; border-radius: 12px; background: #f1f5f9; color: #475569; font-weight: bold; border: 1px solid #cbd5e1; }
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
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        if 'Estado' not in df.columns: df['Estado'] = 'Pendiente'
        df['Estado'] = df['Estado'].astype(str).str.strip()
        df['Estado'] = df['Estado'].apply(lambda x: 'Pendiente' if x in ['', 'None', 'nan'] else x)
        df['Estado_Normalizado'] = df['Estado'].apply(lambda x: 'Completado' if x.lower() == 'completado' else 'Pendiente')
        
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha_Creacion'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce')
        df['Es_Corp'] = (df['Corporativa'].astype(str).str.upper().str.strip() == "SI") | (df['Vendedor'].astype(str).str.upper().str.strip() == "CORPORATIVO")
        
        return df, ws
    except Exception as e:
        st.error(f"Error cargando Excel: {e}")
        return pd.DataFrame(), None

def fmt(n): return f"$ {n:,.0f}".replace(",", ".")

# --- 3. DASHBOARD ---
df, ws = cargar_datos()

if df is not None and not df.empty:
    df_v_total = df[df['Es_Corp'] == False]
    df_c_total = df[df['Es_Corp'] == True]
    ventas_globales = df['Monto_Total'].sum() 

    st.title("📈 Rendimiento de Montos y Saldos")

    # VELOCÍMETRO (Meta Global 150M con colores)
    fig_meta = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = ventas_globales,
        title = {'text': "Meta Global (Equipo + Corp)", 'font': {'size': 18}},
        delta = {'reference': META_VENTAS, 'increasing': {'color': "green"}},
        gauge = {
            'axis': {'range': [None, META_VENTAS], 'tickformat': '$,.0f'},
            'bar': {'color': "#3b82f6"},
            'steps': [
                {'range': [0, META_VENTAS*0.5], 'color': "#fee2e2"},
                {'range': [META_VENTAS*0.5, META_VENTAS*0.8], 'color': "#fef9c3"},
                {'range': [META_VENTAS*0.8, META_VENTAS], 'color': "#dcfce7"}
            ]
        }
    ))
    fig_meta.update_layout(height=230, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig_meta, use_container_width=True)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.subheader("👥 Equipo Ventas")
        st.metric("Subtotal", fmt(df_v_total['Monto_Total'].sum()))
        st.markdown(f"<p class='sub-metrica'>Saldo: <span style='color:#e11d48'>{fmt(df_v_total['Saldo'].sum())}</span></p>", unsafe_allow_html=True)
    with m2:
        st.subheader("🏢 Corporativos")
        st.metric("Subtotal", fmt(df_c_total['Monto_Total'].sum()))
        st.markdown(f"<p class='sub-metrica'>Saldo: <span style='color:#6366f1'>{fmt(df_c_total['Saldo'].sum())}</span></p>", unsafe_allow_html=True)
    with m3:
        st.subheader("🌍 Acumulado Real")
        st.metric("Total Empresa", fmt(ventas_globales))
        st.markdown(f"<p class='sub-metrica'>Deuda Global: <b>{fmt(df['Saldo'].sum())}</b></p>", unsafe_allow_html=True)

    st.divider()

    # CARTERA
    col_l, col_r = st.columns([1.7, 1.3])
    with col_l:
        st.subheader("📑 Cartera de Presupuestos")
        c_filt1, c_filt2 = st.columns(2)
        with c_filt1:
            busc = st.text_input("🔍 Buscar cliente o ppto...")
        with c_filt2:
            ver_completados = st.toggle("Ver historial de Completados", value=False)

        # CORRECCIÓN DE LA LÓGICA DE FILTRADO (Uso de .isin para evitar el ValueError)
        if ver_completados:
            df_view = df.copy()
        else:
            df_view = df[df['Estado_Normalizado'].isin(['Pendiente', 'Pending'])].copy()

        if busc:
            df_view = df_view[df_view.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)]

        if df_view.empty:
            st.info("No hay presupuestos para mostrar.")
        else:
            for i, r in df_view.sort_values(by='Fecha_Creacion', ascending=False).iterrows():
                clase = "card-corp" if r['Es_Corp'] else "card-vendedor"
                st.markdown(f"""
                    <div class="{clase}">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="flex:2;">
                                <span style="font-size:0.8rem; font-weight:bold; color:#64748b;">📅 {r['Fecha_Creacion'].strftime('%d/%m/%Y') if pd.notnull(r['Fecha_Creacion']) else 'S/F'}</span>
                                <span class="status-badge">{r['Estado']}</span><br>
                                <b style="font-size:1.1rem;">{r['Cliente']}</b><br>
                                <small>Ppto: {r['Nro_Ppto']} | Vendedor: {r['Vendedor']}</small>
                            </div>
                            <div style="text-align:right;">
                                <small>Total: {fmt(r['Monto_Total'])}</small><br>
                                <span class="monto-alerta">Saldo: {fmt(r['Saldo'])}</span>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                with st.expander(f"Gestionar {r['Cliente']}"):
                    nt = st.number_input("Total:", value=float(r['Monto_Total']), key=f"t_{i}")
                    np = st.number_input("Cobrado:", value=float(r['Anticipo']), key=f"p_{i}")
                    if st.button("💾 Guardar", key=f"s_{i}"):
                        ws.update_cell(i+2, 4, nt); ws.update_cell(i+2, 5, np); st.rerun()
                    nuevo_st = "Completado" if r['Estado_Normalizado'] == "Pendiente" else "Pendiente"
                    if st.button(f"Pasar a {nuevo_st}", key=f"st_{i}"):
                        ws.update_cell(i+2, 10, nuevo_st); st.rerun()

    with col_r:
        st.subheader("📝 Nuevo Registro")
        with st.form("alta", clear_on_submit=True):
            f_fecha = st.date_input("Fecha", datetime.now())
            f_ppto = st.text_input("Nro Ppto")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jacqueline", "Jonathan", "Roberto", "Corporativo"])
            f_tot = st.number_input("Monto Total", min_value=0.0)
            f_ant = st.number_input("Anticipo", min_value=0.0)
            f_corp = st.checkbox("¿Es Corporativa?")
            if st.form_submit_button("REGISTRAR"):
                ws.append_row([f_fecha.strftime("%Y-%m-%d"), f_ppto, f_cli, f_tot, f_ant, f_ven, "No Facturado", "", "SI" if f_corp else "NO", "Pendiente"])
                st.balloons(); st.rerun()

    st.divider()
    st.subheader("📊 Rendimiento Individual del Equipo")
    g1, g2 = st.columns(2)
    with g1: 
        st.plotly_chart(px.pie(df_v_total, values='Monto_Total', names='Vendedor', title="Ventas Equipo", hole=0.4, color='Vendedor', color_discrete_map=COLORES_VENDEDORES), use_container_width=True)
    with g2: 
        st.plotly_chart(px.bar(df_v_total.groupby('Vendedor')['Anticipo'].sum().reset_index(), x='Vendedor', y='Anticipo', title="Cobranza Equipo", color='Vendedor', color_discrete_map=COLORES_VENDEDORES), use_container_width=True)

else:
    st.error("No hay datos cargados.")