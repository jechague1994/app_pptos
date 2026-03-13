import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Magallan Enterprise - Gestión Total", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8FAFC; }
    .panel-saldos {
        background: white; border: 1px solid #E2E8F0; border-left: 6px solid #0284C7;
        border-radius: 12px; padding: 20px; margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .monto-deuda { color: #E11D48; font-size: 1.3rem; font-weight: 800; }
    .monto-ok { color: #10B981; font-size: 1.3rem; font-weight: 800; }
    .vendedor-tag { background: #EEF2FF; color: #4338CA; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; }
    .factura-tag { background: #FEF3C7; color: #92400E; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin-left: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN Y DATOS ---
@st.cache_resource(ttl=60)
def conectar_gs():
    try:
        return gspread.authorize(Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        ))
    except: return None

def obtener_datos():
    gc = conectar_gs()
    if not gc: return pd.DataFrame(), None
    try:
        sh = gc.open("Gestion_Magallan")
        ws = sh.worksheet("Saldos_Simples")
        df = pd.DataFrame(ws.get_all_records())
        
        cols = ['Fecha', 'Nro_Ppto', 'Cliente', 'Monto_Total', 'Anticipo', 'Vendedor', 'Facturado']
        for c in cols:
            if c not in df.columns: df[c] = "0" if c in ['Monto_Total', 'Anticipo'] else ""
            
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        return df, ws
    except: return pd.DataFrame(), None

df, ws = obtener_datos()

# --- 3. DASHBOARD ---
st.title("📊 Sistema Magallan - Gestión, Rendimiento y Facturación")

if not df.empty:
    with st.sidebar:
        st.header("🔍 Filtros Temporales")
        meses_op = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
        sel_mes = st.multiselect("Filtrar Meses", options=list(meses_op.keys()), format_func=lambda x: meses_op[x], default=list(meses_op.keys()))
        df_view = df[df['Fecha'].dt.month.isin(sel_mes)] if not df['Fecha'].isnull().all() else df

    # Métricas Principales
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VENTAS TOTALES", f"${df_view['Monto_Total'].sum():,.0f}")
    c2.metric("COBRADO", f"${df_view['Anticipo'].sum():,.0f}")
    c3.metric("PENDIENTE", f"${df_view['Saldo'].sum():,.0f}", delta_color="inverse")
    c4.metric("FACTURADO", f"{len(df_view[df_view['Facturado']=='Facturado'])} Pptos")

    # --- SECCIÓN GRÁFICOS ---
    st.subheader("📈 Rendimiento y Perfil de Venta")
    
    # Gráfico 1: Cobranza (Verde/Rojo)
    rend = df_view.groupby('Vendedor').agg({'Monto_Total':'sum', 'Anticipo':'sum', 'Saldo':'sum'}).reset_index()
    
    # Gráfico 2: Facturación (Perfil Estratégico)
    rend_fac = df_view.groupby(['Vendedor', 'Facturado'])['Monto_Total'].sum().reset_index()

    g1, g2 = st.columns([1.5, 1])
    with g1:
        # Gráfico de barras apiladas por facturación
        fig_fac = px.bar(rend_fac, x='Vendedor', y='Monto_Total', color='Facturado',
                         title="Ventas: Facturado vs Sin Facturar",
                         color_discrete_map={'Facturado': '#0284C7', 'Sin Facturar': '#94A3B8'},
                         text_auto='.2s')
        st.plotly_chart(fig_fac, use_container_width=True)
        
    with g2:
        # Cobranza agrupada
        fig_cob = px.bar(rend, x='Vendedor', y=['Anticipo', 'Saldo'], 
                         title="Estado de Cobranza", barmode='group',
                         color_discrete_map={'Anticipo':'#10B981', 'Saldo':'#E11D48'})
        st.plotly_chart(fig_cob, use_container_width=True)

    st.divider()

    # --- CARGA Y GESTIÓN ---
    col_carga, col_lista = st.columns([1, 2])

    with col_carga:
        st.subheader("➕ Nuevo Presupuesto")
        with st.form("form_magallan", clear_on_submit=True):
            f_nro = st.text_input("Nro MAG#")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto"])
            f_tot = st.number_input("Monto Total ($)", min_value=0.0)
            f_ant = st.number_input("Anticipo ($)", min_value=0.0)
            f_fac = st.selectbox("Estado de Facturación", ["Facturado", "Sin Facturar"])
            f_fec = st.date_input("Fecha", value=datetime.now())
            
            if st.form_submit_button("REGISTRAR VENTA"):
                if f_nro and f_cli:
                    ws.append_row([f_fec.strftime("%Y-%m-%d"), f_nro, f_cli, f_tot, f_ant, f_ven, f_fac])
                    st.success("¡Venta registrada!")
                    st.rerun()

    with col_lista:
        st.subheader("📋 Historial de Cuentas")
        busqueda = st.text_input("🔍 Buscar cliente, Nro o vendedor...")
        df_final = df_view[df_view.apply(lambda r: busqueda.lower() in str(r.values).lower(), axis=1)] if busqueda else df_view
        
        for i, r in df_final.sort_values(by='Fecha', ascending=False).iterrows():
            tag_factura = f'<span class="factura-tag">📄 {r["Facturado"]}</span>' if r["Facturado"] == "Facturado" else ""
            clase_monto = "monto-ok" if r['Saldo'] <= 0 else "monto-deuda"
            texto_saldo = f"DEBE: ${r['Saldo']:,.0f}" if r['Saldo'] > 0 else "SALDADO"
            f_disp = r['Fecha'].strftime('%d/%m/%y') if not pd.isnull(r['Fecha']) else "S/F"

            st.markdown(f"""
                <div class="panel-saldos" style="border-left-color: {'#10B981' if r['Saldo'] <= 0 else '#E11D48'}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#64748B; font-size:0.8rem;">{f_disp}</span><br>
                            <b style="font-size:1.1rem;">MAG-{r['Nro_Ppto']} | {r['Cliente']}</b> 
                            <span class="vendedor-tag">👤 {r['Vendedor']}</span>
                            {tag_factura}
                            <br><small style="color:#64748B;">Monto: ${r['Monto_Total']:,.0f} | Cobrado: ${r['Anticipo']:,.0f}</small>
                        </div>
                        <div class="{clase_monto}">{texto_saldo}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander(f"Modificar MAG-{r['Nro_Ppto']}"):
                nc1, nc2 = st.columns(2)
                up_tot = nc1.number_input("Total", value=float(r['Monto_Total']), key=f"tot{i}")
                up_ant = nc2.number_input("Anticipo", value=float(r['Anticipo']), key=f"ant{i}")
                if st.button("Guardar Cambios", key=f"btn{i}"):
                    ws.update_cell(i+2, 4, up_tot)
                    ws.update_cell(i+2, 5, up_ant)
                    st.rerun()