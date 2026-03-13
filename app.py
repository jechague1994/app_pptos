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
        lista_datos = ws.get_all_records()
        
        if not lista_datos:
            st.warning("El Excel parece estar vacío o no tiene encabezados.")
            return pd.DataFrame(), ws

        df = pd.DataFrame(lista_datos)
        
        # Limpieza básica de nombres de columnas (quitar espacios)
        df.columns = [c.strip() for c in df.columns]

        # Asegurar que existan las columnas críticas
        columnas_necesarias = ['Monto_Total', 'Anticipo', 'Vendedor', 'Fecha_Creacion', 'Estado']
        for col in columnas_necesarias:
            if col not in df.columns:
                df[col] = 0 if 'Monto' in col or 'Anticipo' in col else ('Pendiente' if col == 'Estado' else '')

        # Conversiones
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha_Creacion'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce')
        df['Días_Fabricación'] = (datetime.now() - df['Fecha_Creacion']).dt.days.fillna(0).astype(int)
        
        return df, ws
    except Exception as e:
        st.error(f"Error procesando datos: {e}")
        return pd.DataFrame(), None

def fmt(n): return f"$ {n:,.0f}".replace(",", ".")

# --- 3. DASHBOARD ---
df, ws = cargar_datos()

if not df.empty:
    # Sidebar Filtros
    st.sidebar.header("🔍 Control de Vista")
    ver_completados = st.sidebar.checkbox("Ver Historial (Completados)")
    
    lista_vendedores = ["Todos"] + sorted([v for v in df['Vendedor'].unique() if v])
    v_sel = st.sidebar.selectbox("Filtrar Vendedor", lista_vendedores)
    
    # Filtrado Lógico
    estado_buscado = "Completado" if ver_completados else "Pendiente"
    df_f = df[df['Estado'].str.strip() == estado_buscado].copy()
    
    if v_sel != "Todos":
        df_f = df_f[df_f['Vendedor'] == v_sel]

    st.title("📊 Magallan Intelligence Pro")

    # MÉTRICAS
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("TOTAL VENTAS", fmt(df_f['Monto_Total'].sum()))
    m2.metric("TOTAL COBRADO", fmt(df_f['Anticipo'].sum()))
    m3.metric("SALDO PENDIENTE", fmt(df_f['Saldo'].sum()), delta_color="inverse")
    m4.metric("PEDIDOS ACTIVOS", len(df_f))

    st.divider()

    # GRÁFICOS
    if not df_f.empty:
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
        st.subheader("📑 Listado de Clientes")
        busc = st.text_input("🔍 Buscar cliente...")
        df_display = df_f[df_f.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df_f
        
        # Mapeo de columnas para saber dónde escribir
        headers = [h.strip() for h in ws.row_values(1)]
        col_monto = headers.index('Monto_Total') + 1
        col_pago = headers.index('Anticipo') + 1
        col_estado = headers.index('Estado') + 1

        for i, r in df_display.sort_values(by='Fecha_Creacion', ascending=False).iterrows():
            idx_excel = i + 2
            es_corp = str(r.get('Corporativa','')).upper() == "SI"
            dias_f = int(r['Días_Fabricación'])
            clase = "card-corp" if es_corp else ("card-demora" if dias_f > 15 else "card-vendedor")
            
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <b>{r['Cliente']}</b><br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']}</small><br>
                            <small>{'⚠️ DEMORA: ' + str(dias_f) + ' DÍAS' if dias_f > 15 else 'Hace ' + str(dias_f) + ' días'}</small>
                        </div>
                        <div style="text-align:right;">
                            <small>Total: {fmt(r['Monto_Total'])}</small><br>
                            <span class="monto-alerta">Saldo: {fmt(r['Saldo'])}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander(f"⚙️ Editar {r['Cliente']}"):
                c1, c2 = st.columns(2)
                with c1:
                    n_monto = st.number_input("Monto Total:", value=float(r['Monto_Total']), key=f"t_{i}")
                    n_pago = st.number_input("Cobrado:", value=float(r['Anticipo']), key=f"p_{i}")
                    if st.button("💾 Guardar Cambios", key=f"s_{i}"):
                        ws.update_cell(idx_excel, col_monto, n_monto)
                        ws.update_cell(idx_excel, col_pago, n_pago)
                        st.rerun()
                with c2:
                    st.write("Estado actual:", r['Estado'])
                    label_btn = "⏪ Reabrir" if ver_completados else "🏁 Finalizar Trabajo"
                    nuevo_st = "Pendiente" if ver_completados else "Completado"
                    if st.button(label_btn, key=f"st_{i}", use_container_width=True):
                        ws.update_cell(idx_excel, col_estado, nuevo_st)
                        st.rerun()

    with col_r:
        st.subheader("📝 Nuevo Registro")
        with st.form("alta_vta", clear_on_submit=True):
            f_crea = st.date_input("Fecha", datetime.now())
            f_ppto = st.text_input("Nro Ppto")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jacqueline", "Jonathan", "Roberto"])
            f_tot = st.number_input("Monto Total $", min_value=0.0)
            f_ant = st.number_input("Anticipo $", min_value=0.0)
            f_corp = st.checkbox("Corporativa")
            if st.form_submit_button("REGISTRAR"):
                # Asegura el orden: Fecha_Creacion, Nro_Ppto, Cliente, Monto_Total, Anticipo, Vendedor, Facturado, Fecha_Aprobacion, Corporativa, Estado
                ws.append_row([f_crea.strftime("%Y-%m-%d"), f_ppto, f_cli, f_tot, f_ant, f_ven, "No Facturado", datetime.now().strftime("%Y-%m-%d"), "SI" if f_corp else "NO", "Pendiente"])
                st.balloons(); st.rerun()
else:
    st.info("No hay datos para mostrar con los filtros actuales.")