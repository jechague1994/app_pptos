import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Magallan Sistema Pro", layout="wide")

@st.cache_resource(ttl=60)
def conectar_gs():
    try:
        return gspread.authorize(Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        ))
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def obtener_datos():
    gc = conectar_gs()
    if not gc: return pd.DataFrame(), None
    try:
        sh = gc.open("Gestion_Magallan")
        ws = sh.worksheet("Saldos_Simples")
        df = pd.DataFrame(ws.get_all_records())
        
        # BLINDAJE DE COLUMNAS (9 Columnas ahora)
        cols = ['Fecha', 'Nro_Ppto', 'Cliente', 'Monto_Total', 'Anticipo', 'Vendedor', 'Facturado', 'Fecha_Confirmacion', 'Corporativa']
        for c in cols:
            if c not in df.columns: df[c] = ""
        
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df['Fecha_Confirmacion'] = pd.to_datetime(df['Fecha_Confirmacion'], errors='coerce')
        
        # LÓGICA DE ASIGNACIÓN: Si es corporativa, el vendedor para el reporte es "CORPORATIVO"
        df['Vendedor_Reporte'] = df.apply(lambda r: "CORPORATIVO" if str(r['Corporativa']).upper() == "SI" else r['Vendedor'], axis=1)
        
        return df, ws
    except Exception as e:
        st.error(f"Error al leer: {e}")
        return pd.DataFrame(), None

df, ws = obtener_datos()

if not df.empty:
    # FILTROS
    with st.sidebar:
        st.header("⚙️ Panel de Control")
        vendedores_op = ["Todos", "CORPORATIVO"] + sorted([v for v in df['Vendedor'].unique() if v != ""])
        sel_vendedor = st.selectbox("Filtrar Vendedor o Corp.", vendedores_op)
        
    df_f = df[df['Vendedor_Reporte'] == sel_vendedor] if sel_vendedor != "Todos" else df.copy()

    # MÉTRICAS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VENTAS TOTALES", f"${df_f['Monto_Total'].sum():,.0f}")
    c2.metric("COBRADO", f"${df_f['Anticipo'].sum():,.0f}")
    
    # Separación de montos Corporativos vs Vendedores
    monto_corp = df[df['Vendedor_Reporte'] == "CORPORATIVO"]['Monto_Total'].sum()
    monto_vend = df[df['Vendedor_Reporte'] != "CORPORATIVO"]['Monto_Total'].sum()
    
    c3.metric("VENTAS CORP.", f"${monto_corp:,.0f}")
    c4.metric("VENTAS EQUIPO", f"${monto_vend:,.0f}")

    # GRÁFICO DE RENDIMIENTO (Diferenciando Corp)
    st.subheader("📊 Comparativa: Equipo vs Corporativo")
    rend = df.groupby('Vendedor_Reporte').agg({'Monto_Total':'sum', 'Anticipo':'sum'}).reset_index()
    fig = px.bar(rend, x='Vendedor_Reporte', y='Monto_Total', color='Vendedor_Reporte',
                 title="Volumen de Ventas por Origen",
                 color_discrete_map={'CORPORATIVO': '#1E293B'}) # Color oscuro para corporativo
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # FORMULARIO Y LISTADO
    izq, der = st.columns([1, 2.2])
    
    with izq:
        st.subheader("➕ Nueva Venta")
        with st.form("form_corp", clear_on_submit=True):
            f_nro = st.text_input("Nro MAG#")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor (Se ignorará si es Corp.)", ["Jonathan", "Jacqueline", "Roberto"])
            f_corp = st.checkbox("🏢 ¿ES CUENTA CORPORATIVA?")
            f_tot = st.number_input("Total ($)", min_value=0.0)
            f_ant = st.number_input("Anticipo ($)", min_value=0.0)
            f_fac = st.selectbox("Estado Factura", ["Sin Facturar", "Facturado"])
            f_fec_ppto = st.date_input("Fecha del Ppto", datetime.now())
            
            if st.form_submit_button("REGISTRAR VENTA"):
                f_conf = datetime.now().strftime("%Y-%m-%d")
                es_corp = "SI" if f_corp else "NO"
                ws.append_row([f_fec_ppto.strftime("%Y-%m-%d"), f_nro, f_cli, f_tot, f_ant, f_ven, f_fac, f_conf, es_corp])
                st.success("✅ Registrado")
                st.rerun()

    with der:
        st.subheader("📋 Gestión de Saldos")
        buscar = st.text_input("🔍 Buscar...")
        df_list = df_f[df_f.apply(lambda r: buscar.lower() in str(r.values).lower(), axis=1)] if buscar else df_f
        
        for i, r in df_list.sort_values(by='Fecha', ascending=False).iterrows():
            with st.container(border=True):
                # Estilo especial si es corporativa
                if r['Vendedor_Reporte'] == "CORPORATIVO":
                    st.caption("🏢 VENTA CORPORATIVA")
                
                col_info, col_monto = st.columns([3, 1])
                f_ppto = r['Fecha'].strftime('%d/%m/%y') if not pd.isnull(r['Fecha']) else "S/F"
                
                col_info.write(f"*MAG-{r['Nro_Ppto']} | {r['Cliente']}*")
                col_info.caption(f"📅 {f_ppto} | 👤 {r['Vendedor']} | 📄 {r['Facturado']}")
                
                if r['Saldo'] > 0:
                    col_monto.error(f"Debe: ${r['Saldo']:,.0f}")
                else:
                    col_monto.success("SALDADO")
                
                with st.expander("Actualizar"):
                    nt = st.number_input("Monto Total", value=float(r['Monto_Total']), key=f"t{i}")
                    na = st.number_input("Anticipo", value=float(r['Anticipo']), key=f"a{i}")
                    if st.button("Guardar", key=f"b{i}"):
                        ws.update_cell(i+2, 4, nt)
                        ws.update_cell(i+2, 5, na)
                        st.rerun()