import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Magallan Sistema", layout="wide")

# Función de conexión ultra-segura
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
        
        # BLINDAJE: Si faltan columnas, las creamos vacías para que no de KeyError
        columnas_maestras = ['Fecha', 'Nro_Ppto', 'Cliente', 'Monto_Total', 'Anticipo', 'Vendedor', 'Facturado']
        for col in columnas_maestras:
            if col not in df.columns:
                df[col] = 0 if col in ['Monto_Total', 'Anticipo'] else "S/D"
        
        # Limpieza de números
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        
        return df, ws
    except Exception as e:
        st.error(f"Error al leer la hoja: {e}")
        return pd.DataFrame(), None

# --- EJECUCIÓN ---
st.title("📊 Magallan - Gestión de Planta")

df, ws = obtener_datos()

if not df.empty:
    # FILTROS
    with st.sidebar:
        st.header("Filtros")
        vendedores = ["Todos"] + sorted(df['Vendedor'].unique().tolist())
        sel_vendedor = st.selectbox("Filtrar por Vendedor", vendedores)
        
    df_filtrado = df.copy()
    if sel_vendedor != "Todos":
        df_filtrado = df[df['Vendedor'] == sel_vendedor]

    # MÉTRICAS ESTABLES (Sin HTML)
    c1, c2, c3 = st.columns(3)
    c1.metric("VENTAS TOTALES", f"${df_filtrado['Monto_Total'].sum():,.0f}")
    c2.metric("COBRADO", f"${df_filtrado['Anticipo'].sum():,.0f}")
    c3.metric("SALDO PENDIENTE", f"${df_filtrado['Saldo'].sum():,.0f}")

    # RENDIMIENTO
    st.subheader("📈 Rendimiento y Facturación")
    g1, g2 = st.columns(2)
    
    with g1:
        # Gráfico Facturado vs No Facturado
        fig1 = px.bar(df_filtrado.groupby('Facturado')['Monto_Total'].sum().reset_index(), 
                      x='Facturado', y='Monto_Total', color='Facturado', title="Distribución de Facturación")
        st.plotly_chart(fig1, use_container_width=True)
    
    with g2:
        # Cobranza por Vendedor
        fig2 = px.bar(df.groupby('Vendedor')[['Anticipo', 'Saldo']].sum().reset_index(), 
                      x='Vendedor', y=['Anticipo', 'Saldo'], barmode='group', title="Cobranza por Vendedor")
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # FORMULARIO Y LISTADO
    izq, der = st.columns([1, 2])
    
    with izq:
        st.subheader("➕ Cargar Nuevo")
        with st.form("nueva_carga", clear_on_submit=True):
            f_nro = st.text_input("Nro MAG#")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto"])
            f_tot = st.number_input("Total", min_value=0.0)
            f_ant = st.number_input("Anticipo", min_value=0.0)
            f_fac = st.selectbox("Factura", ["Sin Facturar", "Facturado"])
            f_fec = st.date_input("Fecha", datetime.now())
            if st.form_submit_button("Guardar en Excel"):
                ws.append_row([f_fec.strftime("%Y-%m-%d"), f_nro, f_cli, f_tot, f_ant, f_ven, f_fac])
                st.success("¡Registrado!")
                st.rerun()

    with der:
        st.subheader("📋 Listado de Saldos")
        buscar = st.text_input("🔍 Buscar Cliente o Nro...")
        df_final = df_filtrado[df_filtrado.apply(lambda r: buscar.lower() in str(r.values).lower(), axis=1)] if buscar else df_filtrado
        
        for i, r in df_final.iterrows():
            # Usamos componentes nativos de Streamlit para evitar fallos de HTML
            with st.container(border=True):
                col_a, col_b = st.columns([3, 1])
                col_a.write(f"*MAG-{r['Nro_Ppto']} | {r['Cliente']}*")
                col_a.caption(f"Vendedor: {r['Vendedor']} | {r['Facturado']}")
                col_b.write(f"*Saldo: ${r['Saldo']:,.0f}*")
                
                with st.expander("Editar Montos"):
                    new_t = st.number_input("Total", value=float(r['Monto_Total']), key=f"t{i}")
                    new_a = st.number_input("Anticipo", value=float(r['Anticipo']), key=f"a{i}")
                    if st.button("Actualizar", key=f"b{i}"):
                        ws.update_cell(i+2, 4, new_t)
                        ws.update_cell(i+2, 5, new_a)
                        st.rerun()
else:
    st.warning("No hay datos para mostrar. Asegúrate de que el Excel 'Gestion_Magallan' tiene la hoja 'Saldos_Simples' con datos.")