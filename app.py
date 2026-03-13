import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Magallan Dashboard Pro", layout="wide", page_icon="📈")

# Colores Pastel Fijos
COLORES_VENDEDORES = {
    "Jacqueline": "#FFB6C1", # Rosa Pastel
    "Jonathan": "#ADD8E6",   # Azul Pastel
    "Roberto": "#98FB98"     # Verde Pastel
}

# CSS Limpio para evitar errores de sintaxis
estilos = """
<style>
    div[data-testid="stMetric"] {
        background-color: white !important;
        padding: 15px !important;
        border-radius: 10px !important;
        border: 1px solid #e2e8f0 !important;
    }
    .card-vendedor { 
        background-color: white; 
        border-radius: 10px; 
        padding: 18px; 
        margin-bottom: 12px; 
        border-left: 6px solid #3b82f6; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.08); 
    }
    .card-demora { 
        background-color: #fef9c3; 
        border-radius: 10px; 
        padding: 18px; 
        margin-bottom: 12px; 
        border-left: 6px solid #facc15; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
    }
    .card-corp { 
        background-color: #1e293b; 
        color: white; 
        border-radius: 10px; 
        padding: 18px; 
        margin-bottom: 12px; 
        border-left: 6px solid #6366f1; 
    }
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
        
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        
        # Fecha de creación y cálculo de días (No se detiene)
        df['Fecha_Creacion'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce')
        ahora = datetime.now()
        df['Días_Fabricación'] = (ahora - df['Fecha_Creacion']).dt.days.fillna(0).astype(int)
        
        return df, ws
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
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
    avg_fab = df_f['Días_Fabricación'].mean()
    m4.metric("PROM. FABRICACIÓN", f"{avg_fab:.1f} días" if not pd.isna(avg_fab) else "0 días")

    st.divider()

    # --- GRÁFICOS ---
    g1, g2, g3 = st.columns(3)
    with g1:
        fig1 = px.pie(df_f, values='Monto_Total', names='Vendedor', title="Ventas por Vendedor (%)", hole=0.5, color='Vendedor', color_discrete_map=COLORES_VENDEDORES)
        st.plotly_chart(fig1, use_container_width=True)
    with g2:
        fig2 = px.pie(df_f, values='Monto_Total', names='Facturado', title="Distribución Facturación", color='Facturado', color_discrete_map={"Facturado": "#2ecc71", "No Facturado": "#e74c3c"})
        st.plotly_chart(fig2, use_container_width=True)
    with g3:
        df_rank = df_f.groupby('Vendedor')['Anticipo'].sum().reset_index().sort_values('Anticipo')
        fig3 = px.bar(df_rank, y='Vendedor', x='Anticipo', orientation='h', title="Recaudación por Vendedor", color='Vendedor', color_discrete_map=COLORES_VENDEDORES)
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # --- OPERATIVA ---
    col_l, col_r = st.columns([1.7, 1.3])

    with col_l:
        st.subheader("📑 Cartera de Clientes")
        busc = st.text_input("🔍 Buscar por nombre o Ppto...")
        df_v = df_f[df_f.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df_f
        
        for i, r in df_v.sort_values(by='Fecha_Creacion', ascending=False).iterrows():
            es_corp = str(r.get('Corporativa','')).upper() == "SI"
            dias_f = int(r['Días_Fabricación'])
            
            # Lógica de color de tarjeta (Prioridad: Corp > Demora > Normal)
            if es_corp:
                clase = "card-corp"
                monto_clase = "monto-corp"
            elif dias_f > 15:
                clase = "card-demora"
                monto_clase = "monto-alerta"
            else:
                clase = "card-vendedor"
                monto_clase = "monto-alerta"
            
            tag_demora = f'<span class="tag-demora">⚠️ DEMORA: {dias_f} DÍAS</span>' if dias_f > 15 else f'<span>Hace {dias_f} días</span>'
            
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <b>{r['Cliente']}</b><br>
                            <small>Ppto: {r['Nro_Ppto']} | {r['Vendedor']}</small><br>
                            <small>{tag_demora}</small>
                        </div>
                        <div style="text-align:right;">
                            <span class="{monto_clase}">{fmt(r['Saldo'])}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander(f"Actualizar saldo: {r['Cliente']}"):
                nv = st.number_input(f"Nuevo total cobrado:", value=float(r['Anticipo']), step=1000.0, key=f"e_{i}")
                if st.button("Guardar Cambios", key=f"b_{i}"):
                    ws.update_cell(i+2, 5, nv)
                    st.success("¡Actualizado!"); st.rerun()

    with col_r:
        st.subheader("📝 Registrar Nueva Venta")
        with st.form("alta", clear_on_submit=True):
            f_crea = st.date_input("Fecha Creación", datetime.now())
            f_ppto = st.text_input("Nro Presupuesto")
            f_cli = st.text_input("Nombre del Cliente")
            f_ven = st.selectbox("Vendedor Responsable", ["Jacqueline", "Jonathan", "Roberto"])
            f_fac = st.selectbox("Facturación", ["Facturado", "No Facturado"])
            f_tot = st.number_input("Monto Total ($)", min_value=0.0)
            f_ant = st.number_input("Pago/Anticipo ($)", min_value=0.0)
            f_corp = st.checkbox("¿Es Cuenta Corporativa?")
            if st.form_submit_button("REGISTRAR OPERACIÓN"):
                f_apro = datetime.now().strftime("%Y-%m-%d %H:%M")
                ws.append_row([f_crea.strftime("%Y-%m-%d"), f_ppto, f_cli, f_tot, f_ant, f_ven, f_fac, f_apro, "SI" if f_corp else "NO"])
                st.balloons(); st.rerun()
else:
    st.warning("No se encontraron registros en el archivo de Google Sheets.")