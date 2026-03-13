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
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        return df, ws
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
        return pd.DataFrame(), None

# --- 3. PROCESAMIENTO Y FILTROS ---
df, ws = cargar_datos()

if not df.empty:
    # --- BARRA LATERAL (FILTROS) ---
    st.sidebar.header("🔍 Filtros Globales")
    vendedores = ["Todos"] + list(df['Vendedor'].unique())
    vendedor_sel = st.sidebar.selectbox("Filtrar por Vendedor", vendedores)
    
    # Aplicar Filtro
    df_filtered = df.copy()
    if vendedor_sel != "Todos":
        df_filtered = df_filtered[df_filtered['Vendedor'] == vendedor_sel]

    st.title(f"📊 Panel Magallan - {vendedor_sel}")

    # --- MÉTRICAS ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS TOTALES", f"${df_filtered['Monto_Total'].sum():,.0f}")
    m2.metric("TOTAL COBRADO", f"${df_filtered['Anticipo'].sum():,.0f}")
    m3.metric("SALDO PENDIENTE", f"${df_filtered['Saldo'].sum():,.0f}", delta_color="inverse")
    m4.metric("PEDIDOS", len(df_filtered))

    st.divider()

    # --- SECCIÓN DE GRÁFICOS (ARRIBA) ---
    g1, g2, g3 = st.columns(3)

    with g1:
        # 1. Gráfico de Torta: Vendedores
        fig_pie = px.pie(df_filtered, values='Monto_Total', names='Vendedor', 
                         title="Participación de Ventas", hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    with g2:
        # 2. Gráfico de Barras: Facturación (Opciones Correctas)
        df_f_chart = df_filtered.groupby('Facturado')['Monto_Total'].sum().reset_index()
        fig_bar = px.bar(df_f_chart, x='Facturado', y='Monto_Total', color='Facturado',
                         title="Estado de Facturación", 
                         color_discrete_map={"Facturado": "#3b82f6", "Sin Factura": "#94a3b8"})
        st.plotly_chart(fig_bar, use_container_width=True)

    with g3:
        # 3. Gráfico de Área: Tendencia Temporal
        df_t = df_filtered.dropna(subset=['Fecha']).sort_values('Fecha')
        df_t['Mes'] = df_t['Fecha'].dt.strftime('%b %y')
        df_line = df_t.groupby('Mes')['Monto_Total'].sum().reset_index()
        fig_area = px.area(df_line, x='Mes', y='Monto_Total', title="Evolución de Ingresos", markers=True)
        st.plotly_chart(fig_area, use_container_width=True)

    st.divider()

    # --- SECCIÓN OPERATIVA (ABAJO) ---
    col_lista, col_form = st.columns([1.8, 1.2])

    with col_lista:
        st.subheader("📑 Cartera de Pedidos")
        busc = st.text_input("🔍 Buscar cliente o número de presupuesto...")
        df_view = df_filtered[df_filtered.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df_filtered
        
        for i, r in df_view.sort_values(by='Fecha', ascending=False).iterrows():
            clase = "card-corp" if str(r.get('Corporativa','')).upper() == "SI" else "card-vendedor"
            st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="flex:2;">
                            <span style="font-size:1.15rem; font-weight:bold;">{r['Cliente']}</span><br>
                            <small>Ppto: {r['Nro_Ppto']} | Vendedor: {r['Vendedor']} | {r['Facturado']}</small>
                        </div>
                        <div style="text-align:right;">
                            <span class="monto-alerta">${r['Saldo']:,.0f}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander(f"Actualizar pago de {r['Cliente']}"):
                nv = st.number_input("Nuevo total cobrado", value=float(r['Anticipo']), key=f"pay_{i}")
                if st.button("Confirmar Pago", key=f"btn_{i}"):
                    # Buscamos la fila original en el Excel
                    # i es el índice del dataframe original
                    ws.update_cell(i+2, 5, nv)
                    st.success("Cobro actualizado")
                    st.rerun()

    with col_form:
        st.subheader("📝 Registrar Nueva Venta")
        with st.form("form_alta", clear_on_submit=True):
            f_ppto = st.text_input("Nro Presupuesto")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto", "Distribuidor"])
            f_fac = st.selectbox("Estado Factura", ["Facturado", "Sin Factura"])
            f_tot = st.number_input("Monto Total $", min_value=0.0)
            f_ant = st.number_input("Anticipo $", min_value=0.0)
            f_corp = st.checkbox("¿Es Cuenta Corporativa?")
            
            if st.form_submit_button("REGISTRAR VENTA"):
                hoy = datetime.now().strftime("%Y-%m-%d")
                ws.append_row([hoy, f_ppto, f_cli, f_tot, f_ant, f_ven, f_fac, hoy, "SI" if f_corp else "NO"])
                st.balloons()
                st.rerun()
else:
    st.warning("No se encontraron datos. Verifica la conexión con Google Sheets.")