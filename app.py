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
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # BLINDAJE DE COLUMNAS
        cols = ['Fecha', 'Nro_Ppto', 'Cliente', 'Monto_Total', 'Anticipo', 'Vendedor', 'Facturado', 'Fecha_Confirmacion']
        for c in cols:
            if c not in df.columns: df[c] = ""
        
        # Limpieza de datos
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        
        # Procesamiento de Fechas
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df['Fecha_Confirmacion'] = pd.to_datetime(df['Fecha_Confirmacion'], errors='coerce')
        
        # Cálculo de días (Antigüedad desde la fecha del presupuesto)
        hoy = pd.Timestamp(datetime.now().date())
        df['Dias_Pasados'] = (hoy - df['Fecha']).dt.days.fillna(0).astype(int)
        
        return df, ws
    except Exception as e:
        st.error(f"Error al leer: {e}")
        return pd.DataFrame(), None

# --- EJECUCIÓN ---
st.title("🚀 Magallan - Control de Ventas y Cobranzas")

df, ws = obtener_datos()

if not df.empty:
    # FILTROS Y ANÁLISIS DE DEUDA
    with st.sidebar:
        st.header("Filtros")
        vendedores = ["Todos"] + sorted(df['Vendedor'].unique().tolist())
        sel_vendedor = st.selectbox("Vendedor", vendedores)
        
    df_f = df[df['Vendedor'] == sel_vendedor] if sel_vendedor != "Todos" else df.copy()

    # MÉTRICAS ESTRATÉGICAS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VENTAS TOTALES", f"${df_f['Monto_Total'].sum():,.0f}")
    c2.metric("COBRADO", f"${df_f['Anticipo'].sum():,.0f}")
    
    # Análisis de Deuda Joven vs Vieja
    deuda_vieja = df_f[(df_f['Dias_Pasados'] > 30) & (df_f['Saldo'] > 0)]['Saldo'].sum()
    c3.metric("DEUDA +30 DÍAS", f"${deuda_vieja:,.0f}", delta="Crítico", delta_color="inverse")
    c4.metric("PENDIENTE TOTAL", f"${df_f['Saldo'].sum():,.0f}")

    # GRÁFICO DE ANTIGÜEDAD
    st.subheader("📊 Análisis de Antigüedad de Deuda")
    df_f['Estado_Deuda'] = df_f.apply(lambda r: 'Al día' if r['Saldo'] <= 0 else ('Crítica (+30d)' if r['Dias_Pasados'] > 30 else 'Reciente'), axis=1)
    fig_deuda = px.pie(df_f[df_f['Saldo']>0], values='Saldo', names='Estado_Deuda', 
                       color='Estado_Deuda', color_discrete_map={'Crítica (+30d)':'#E11D48', 'Reciente':'#F59E0B'})
    st.plotly_chart(fig_deuda, use_container_width=True)

    st.divider()

    # INTERFAZ DE CARGA Y LISTADO
    izq, der = st.columns([1, 2])
    
    with izq:
        st.subheader("➕ Nueva Venta")
        with st.form("form_v2", clear_on_submit=True):
            f_nro = st.text_input("Nro MAG#")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto"])
            f_tot = st.number_input("Total ($)", min_value=0.0)
            f_ant = st.number_input("Anticipo ($)", min_value=0.0)
            f_fac = st.selectbox("Factura", ["Sin Facturar", "Facturado"])
            f_fec_ppto = st.date_input("Fecha del Presupuesto", datetime.now())
            
            if st.form_submit_button("REGISTRAR VENTA"):
                # La fecha de confirmación se toma automáticamente hoy
                f_conf = datetime.now().strftime("%Y-%m-%d")
                ws.append_row([f_fec_ppto.strftime("%Y-%m-%d"), f_nro, f_cli, f_tot, f_ant, f_ven, f_fac, f_conf])
                st.success("✅ Venta Confirmada y Registrada")
                st.rerun()

    with der:
        st.subheader("📋 Gestión de Saldos y Fechas")
        buscar = st.text_input("🔍 Buscar por cliente o Nro...")
        df_list = df_f[df_f.apply(lambda r: buscar.lower() in str(r.values).lower(), axis=1)] if buscar else df_f
        
        for i, r in df_list.sort_values(by='Fecha', ascending=False).iterrows():
            with st.container(border=True):
                col_info, col_monto = st.columns([3, 1])
                
                # Formateo de fechas para el listado
                f_ppto = r['Fecha'].strftime('%d/%m/%y') if not pd.isnull(r['Fecha']) else "S/F"
                f_conf = r['Fecha_Confirmacion'].strftime('%d/%m/%y') if not pd.isnull(r['Fecha_Confirmacion']) else "S/F"
                
                col_info.write(f"*MAG-{r['Nro_Ppto']} | {r['Cliente']}*")
                col_info.caption(f"📅 Ppto: {f_ppto} | ✅ Confirmado: {f_conf} ({r['Dias_Pasados']} días)")
                col_info.write(f"👤 {r['Vendedor']} | 📄 {r['Facturado']}")
                
                if r['Saldo'] > 0:
                    col_monto.error(f"Debe: ${r['Saldo']:,.0f}")
                else:
                    col_monto.success("SALDADO")
                
                with st.expander("Actualizar Importes"):
                    nt = st.number_input("Nuevo Total", value=float(r['Monto_Total']), key=f"t{i}")
                    na = st.number_input("Nuevo Anticipo", value=float(r['Anticipo']), key=f"a{i}")
                    if st.button("Guardar", key=f"b{i}"):
                        ws.update_cell(i+2, 4, nt)
                        ws.update_cell(i+2, 5, na)
                        st.rerun()