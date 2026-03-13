import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Magallan Dashboard Pro", layout="wide", page_icon="📈")

COLORES_VENDEDORES = {"Jacqueline": "#FFB6C1", "Jonathan": "#ADD8E6", "Roberto": "#98FB98"}

estilos = """
<style>
    div[data-testid="stMetric"] { background-color: white !important; padding: 15px !important; border-radius: 10px !important; border: 1px solid #e2e8f0 !important; }
    .card-vendedor { background-color: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #3b82f6; box-shadow: 0 2px 5px rgba(0,0,0,0.08); }
    .card-demora { background-color: #fef9c3; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #facc15; }
    .card-corp { background-color: #1e293b; color: white; border-radius: 10px; padding: 18px; margin-bottom: 12px; border-left: 6px solid #6366f1; }
    .monto-alerta { color: #e11d48; font-weight: 800; font-size: 1.2rem; }
    .monto-corp { color: #818cf8; font-weight: 800; font-size: 1.2rem; }
    .tag-demora { background-color: #fef08a; color: #854d0e; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: bold; }
</style>
"""
st.markdown(estilos, unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
@st.cache_resource(ttl=30)
def conectar_gs():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error de credenciales: {e}")
        return None

def cargar_datos():
    gc = conectar_gs()
    if not gc: return pd.DataFrame(), None
    try:
        sh = gc.open("Gestion_Magallan")
        ws = sh.worksheet("Saldos_Simples")
        df = pd.DataFrame(ws.get_all_records())
        
        # Asegurar columna de Estado
        if 'Estado' not in df.columns:
            df['Estado'] = 'Pendiente'
        
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha_Creacion'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce')
        df['Días_Fabricación'] = (datetime.now() - df['Fecha_Creacion']).dt.days.fillna(0).astype(int)
        
        return df, ws
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
        return pd.DataFrame(), None

def fmt(n): return f"$ {n:,.0f}".replace(",", ".")

# --- 3. DASHBOARD ---
df, ws = cargar_datos()

if not df.empty:
    # FILTROS
    st.sidebar.header("🔍 Filtros")
    ver_completados = st.sidebar.checkbox("Ver trabajos completados")
    v_sel = st.sidebar.selectbox("Vendedor", ["Todos"] + sorted(list(df['Vendedor'].unique())))
    
    # Filtrado por Estado y Vendedor
    df_f = df.copy()
    if not ver_completados:
        df_f = df_f[df_f['Estado'] != 'Completado']
    else:
        df_f = df_f[df_f['Estado'] == 'Completado']
        
    if v_sel != "Todos":
        df_f = df_f[df_f['Vendedor'] == v_sel]

    st.title("📊 Magallan Intelligence Pro")

    # MÉTRICAS
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS TOTALES", fmt(df_f['Monto_Total'].sum()))
    m2.metric("RECAUDADO", fmt(df_f['Anticipo'].sum()))
    m3.metric("DEUDA PENDIENTE", fmt(df_f['Saldo'].sum()), delta_color="inverse")
    m4.metric("TRABAJOS", len(df_f))

    st.divider()

    # --- OPERATIVA ---
    col_l, col_r = st.columns([1.7, 1.3])

    with col_l:
        st.subheader("📑 Gestión de Trabajos")
        busc = st.text_input("🔍 Buscar por nombre o Ppto...")
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
                            <b>{r['Cliente']}</b> {'✅' if r['Estado'] == 'Completado' else ''}<br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']}</small><br>
                            <small>{f'⚠️ DEMORA: {dias_f} DÍAS' if dias_f > 15 else f'Hace {dias_f} días'}</small>
                        </div>
                        <div style="text-align:right;">
                            <span class="{monto_clase}">{fmt(r['Saldo'])}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander(f"Acciones para: {r['Cliente']}"):
                c1, c2 = st.columns(2)
                with c1:
                    nv = st.number_input(f"Cobrado:", value=float(r['Anticipo']), key=f"e_{i}")
                    if st.button("Guardar Cobro", key=f"b_{i}"):
                        ws.update_cell(i+2, 5, nv)
                        st.rerun()
                with c2:
                    if r['Estado'] != 'Completado':
                        if st.button("🏁 COMPLETAR TRABAJO", key=f"comp_{i}"):
                            # Asumiendo que Estado es la columna 10 (J)
                            # Si no existe la columna en el Excel físico, hay que crearla.
                            ws.update_cell(i+2, 10, "Completado")
                            st.success("¡Trabajo finalizado!"); st.rerun()
                    else:
                        if st.button("⏪ Reabrir Trabajo", key=f"reab_{i}"):
                            ws.update_cell(i+2, 10, "Pendiente")
                            st.rerun()

    with col_r:
        st.subheader("📝 Nueva Venta")
        with st.form("alta", clear_on_submit=True):
            f_crea = st.date_input("Fecha Creación", datetime.now())
            f_ppto = st.text_input("Nro Presupuesto")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jacqueline", "Jonathan", "Roberto"])
            f_fac = st.selectbox("Facturación", ["Facturado", "No Facturado"])
            f_tot = st.number_input("Monto Total ($)", min_value=0.0)
            f_ant = st.number_input("Anticipo ($)", min_value=0.0)
            f_corp = st.checkbox("¿Es Cuenta Corporativa?")
            if st.form_submit_button("REGISTRAR"):
                f_apro = datetime.now().strftime("%Y-%m-%d %H:%M")
                # Se agrega "Pendiente" al final de la fila
                ws.append_row([f_crea.strftime("%Y-%m-%d"), f_ppto, f_cli, f_tot, f_ant, f_ven, f_fac, f_apro, "SI" if f_corp else "NO", "Pendiente"])
                st.balloons(); st.rerun()
else:
    st.warning("No se encontraron registros.")