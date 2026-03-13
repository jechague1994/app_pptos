import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Magallan Dashboard Pro", layout="wide", page_icon="📈")

COLORES_VENDEDORES = {"Jacqueline": "#FFB6C1", "Jonathan": "#ADD8E6", "Roberto": "#98FB98"}

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: white !important; padding: 15px !important; border-radius: 10px !important; border: 1px solid #e2e8f0 !important; }
    .card-vendedor { background-color: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #3b82f6; box-shadow: 0 2px 5px rgba(0,0,0,0.08); }
    .card-demora { background-color: #fef9c3; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #facc15; }
    .card-corp { background-color: #1e293b; color: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #6366f1; }
    .monto-alerta { color: #e11d48; font-weight: 800; font-size: 1.2rem; }
    .monto-corp { color: #818cf8; font-weight: 800; font-size: 1.2rem; }
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
        
        # Si la columna Estado no existe en el Excel, la creamos en el DataFrame
        if 'Estado' not in df.columns: df['Estado'] = 'Pendiente'
        
        # Limpieza de datos
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha_Creacion'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce')
        df['Días_Fabricación'] = (datetime.now() - df['Fecha_Creacion']).dt.days.fillna(0).astype(int)
        
        return df, ws
    except Exception as e:
        st.error(f"Error cargando Excel: {e}")
        return pd.DataFrame(), None

def fmt(n): return f"$ {n:,.0f}".replace(",", ".")

# --- 3. DASHBOARD ---
df, ws = cargar_datos()

if df is not None and not df.empty:
    st.sidebar.header("🔍 Filtros")
    ver_completados = st.sidebar.checkbox("Ver trabajos COMPLETADOS")
    v_sel = st.sidebar.selectbox("Vendedor", ["Todos"] + sorted(list(df['Vendedor'].unique())))
    
    # Filtrar por estado: Si el campo está vacío, lo tratamos como 'Pendiente'
    df['Estado_Limpio'] = df['Estado'].apply(lambda x: 'Completado' if str(x).strip() == 'Completado' else 'Pendiente')
    
    estado_filtro = 'Completado' if ver_completados else 'Pendiente'
    df_f = df[df['Estado_Limpio'] == estado_filtro].copy()
    
    if v_sel != "Todos":
        df_f = df_f[df_f['Vendedor'] == v_sel]

    st.title("📊 Magallan Intelligence Pro")

    # MÉTRICAS
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS TOTALES", fmt(df_f['Monto_Total'].sum()))
    m2.metric("RECAUDADO", fmt(df_f['Anticipo'].sum()))
    m3.metric("DEUDA PENDIENTE", fmt(df_f['Saldo'].sum()), delta_color="inverse")
    m4.metric("PEDIDOS", len(df_f))

    st.divider()

    # GRÁFICOS
    g1, g2, g3 = st.columns(3)
    with g1:
        st.plotly_chart(px.pie(df_f, values='Monto_Total', names='Vendedor', title="Cuota Ventas", hole=0.5, color='Vendedor', color_discrete_map=COLORES_VENDEDORES), use_container_width=True)
    with g2:
        st.plotly_chart(px.pie(df_f, values='Monto_Total', names='Facturado', title="Facturación", color='Facturado', color_discrete_map={"Facturado": "#A7F3D0", "No Facturado": "#FCA5A5"}), use_container_width=True)
    with g3:
        df_rank = df_f.groupby('Vendedor')['Anticipo'].sum().reset_index()
        st.plotly_chart(px.bar(df_rank, y='Vendedor', x='Anticipo', orientation='h', title="Ranking Cobranza", color='Vendedor', color_discrete_map=COLORES_VENDEDORES), use_container_width=True)

    st.divider()

    # OPERATIVA
    col_l, col_r = st.columns([1.7, 1.3])

    with col_l:
        st.subheader("📑 Gestión de Cartera")
        busc = st.text_input("🔍 Buscar cliente...")
        df_v = df_f[df_f.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df_f
        
        for i, r in df_v.sort_values(by='Fecha_Creacion', ascending=False).iterrows():
            es_corp = str(r.get('Corporativa','')).upper() == "SI"
            dias_f = int(r['Días_Fabricación'])
            clase = "card-corp" if es_corp else ("card-demora" if dias_f > 15 else "card-vendedor")
            monto_clase = "monto-corp" if es_corp else "monto-alerta"

            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <b>{r['Cliente']}</b> {'✅' if r['Estado_Limpio'] == 'Completado' else ''}<br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']}</small><br>
                            <small>{'⚠️ DEMORA: ' + str(dias_f) + ' DÍAS' if dias_f > 15 else 'Hace ' + str(dias_f) + ' días'}</small>
                        </div>
                        <div style="text-align:right;">
                            <small>Total: {fmt(r['Monto_Total'])}</small><br>
                            <span class="{monto_clase}">Saldo: {fmt(r['Saldo'])}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander(f"Editar {r['Cliente']}"):
                # Columnas fijas de edición (basado en el orden estándar del Excel)
                n_total = st.number_input("Monto Total:", value=float(r['Monto_Total']), key=f"t_{i}")
                n_pago = st.number_input("Anticipo/Pago:", value=float(r['Anticipo']), key=f"p_{i}")
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("💾 Guardar Cambios", key=f"s_{i}"):
                        ws.update_cell(i+2, 4, n_total) # Columna D
                        ws.update_cell(i+2, 5, n_pago)  # Columna E
                        st.rerun()
                with c2:
                    label = "⏪ Reabrir" if r['Estado_Limpio'] == 'Completado' else "🏁 Completar"
                    nuevo_st = "Pendiente" if r['Estado_Limpio'] == 'Completado' else "Completado"
                    if st.button(label, key=f"st_{i}"):
                        ws.update_cell(i+2, 10, nuevo_st) # Columna J
                        st.rerun()

    with col_r:
        st.subheader("📝 Nuevo Registro")
        with st.form("alta", clear_on_submit=True):
            f_crea = st.date_input("Fecha", datetime.now())
            f_ppto = st.text_input("Nro Ppto")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jacqueline", "Jonathan", "Roberto"])
            f_tot = st.number_input("Total $", min_value=0.0)
            f_ant = st.number_input("Anticipo $", min_value=0.0)
            f_corp = st.checkbox("Corporativa")
            if st.form_submit_button("REGISTRAR"):
                ws.append_row([f_crea.strftime("%Y-%m-%d"), f_ppto, f_cli, f_tot, f_ant, f_ven, "No Facturado", datetime.now().strftime("%Y-%m-%d"), "SI" if f_corp else "NO", "Pendiente"])
                st.balloons(); st.rerun()
else:
    st.warning("No se detectan datos. Verifica que el Excel tenga los encabezados en la fila 1.")