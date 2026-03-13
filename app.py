import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Magallan Enterprise - Control Total", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F1F5F9; }
    .panel-saldos {
        background: white; border: 1px solid #E2E8F0; border-left: 6px solid #0284C7;
        border-radius: 8px; padding: 15px; margin-bottom: 8px;
    }
    .monto-deuda { color: #E11D48; font-size: 1.1rem; font-weight: 700; }
    .monto-ok { color: #10B981; font-size: 1.1rem; font-weight: 700; }
    .vendedor-tag { background: #E0E7FF; color: #4338CA; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .iva-tag { background: #FDE68A; color: #92400E; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-left: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
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
        
        # Validación de columnas incluyendo la nueva de IVA
        cols = ['Fecha', 'Nro_Ppto', 'Cliente', 'Monto_Total', 'Anticipo', 'Vendedor', 'IVA']
        for c in cols:
            if c not in df.columns: df[c] = ""
            
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        return df, ws
    except: return pd.DataFrame(), None

# --- 3. LÓGICA ---
df, ws = obtener_datos()

st.title("🚀 Magallan: Control de Gestión & Rendimiento")

if not df.empty:
    # Sidebar con filtros
    with st.sidebar:
        st.header("⚙️ Filtros")
        meses = {1:'Ene', 2:'Feb', 3:'Mar', 4:'Abr', 5:'May', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dic'}
        sel_mes = st.multiselect("Mes", options=list(meses.keys()), format_func=lambda x: meses[x], default=list(meses.keys()))
        df_view = df[df['Fecha'].dt.month.isin(sel_mes)] if not df['Fecha'].isnull().all() else df
        
    # Métricas
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS", f"${df_view['Monto_Total'].sum():,.0f}")
    m2.metric("COBRADO", f"${df_view['Anticipo'].sum():,.0f}")
    m3.metric("A COBRAR", f"${df_view['Saldo'].sum():,.0f}", delta_color="inverse")
    m4.metric("EFICACIA", f"{(df_view['Anticipo'].sum()/df_view['Monto_Total'].sum()*100 if df_view['Monto_Total'].sum()>0 else 0):.1f}%")

    # Gráficos de Rendimiento
    rend_vendedor = df_view.groupby('Vendedor').agg({'Monto_Total':'sum', 'Anticipo':'sum', 'Saldo':'sum'}).reset_index()
    c_g1, c_g2 = st.columns([2, 1])
    with c_g1:
        st.plotly_chart(px.bar(rend_vendedor, x='Vendedor', y=['Anticipo', 'Saldo'], barmode='group', color_discrete_sequence=['#10B981', '#E11D48']), use_container_width=True)
    with c_g2:
        st.plotly_chart(px.pie(rend_vendedor, values='Monto_Total', names='Vendedor', hole=0.4), use_container_width=True)

    st.divider()

    # Carga y Listado
    col_f, col_l = st.columns([1, 2])

    with col_f:
        st.subheader("➕ Nuevo Registro")
        with st.form("form_iva", clear_on_submit=True):
            f_nro = st.text_input("Nro MAG#")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto"])
            f_tot = st.number_input("Monto Total ($)", min_value=0.0)
            f_ant = st.number_input("Anticipo ($)", min_value=0.0)
            f_fec = st.date_input("Fecha", value=datetime.now())
            f_iva = st.checkbox("¿Es con IVA?") # Nuevo campo solicitado
            
            if st.form_submit_button("REGISTRAR"):
                txt_iva = "SI" if f_iva else "NO"
                ws.append_row([f_fec.strftime("%Y-%m-%d"), f_nro, f_cli, f_tot, f_ant, f_ven, txt_iva])
                st.success("Guardado")
                st.rerun()

    with col_l:
        st.subheader("📋 Gestión de Saldos")
        buscar = st.text_input("🔍 Buscar...")
        df_list = df_view[df_view.apply(lambda r: buscar.lower() in str(r.values).lower(), axis=1)] if buscar else df_view
        
        for i, r in df_list.sort_values(by='Fecha', ascending=False).iterrows():
            badge_iva = f'<span class="iva-tag">CON IVA</span>' if str(r['IVA']).upper() == "SI" else ""
            
            st.markdown(f"""
                <div class="panel-saldos" style="border-left-color: {'#10B981' if r['Saldo'] <= 0 else '#E11D48'}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <b>MAG-{r['Nro_Ppto']} | {r['Cliente']}</b> 
                            <span class="vendedor-tag">👤 {r['Vendedor']}</span>
                            {badge_iva}
                            <br><small>📅 {r['Fecha'].strftime('%d/%m/%y') if not pd.isnull(r['Fecha']) else 'S/F'} | Total: ${r['Monto_Total']:,.0f}</small>
                        </div>
                        <div class="{'monto-ok' if r['Saldo'] <= 0 else 'monto-deuda'}">
                            {'$' + str(f"{r['Saldo']:,.0f}") if r['Saldo'] > 0 else 'SALDADO'}
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Actualizar montos"):
                u_tot = st.number_input("Total", value=float(r['Monto_Total']), key=f"ut{i}")
                u_ant = st.number_input("Anticipo", value=float(r['Anticipo']), key=f"ua{i}")
                if st.button("Guardar", key=f"ub{i}"):
                    ws.update_cell(i+2, 4, u_tot)
                    ws.update_cell(i+2, 5, u_ant)
                    st.rerun()