import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Magallan Enterprise - Control Total", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8FAFC; }
    /* Tarjeta Normal */
    .card-vendedor {
        background: white; border: 1px solid #E2E8F0; border-left: 6px solid #0284C7;
        border-radius: 12px; padding: 18px; margin-bottom: 12px;
    }
    /* Tarjeta Corporativa */
    .card-corp {
        background: #F1F5F9; border: 1px solid #CBD5E1; border-left: 6px solid #1E293B;
        border-radius: 12px; padding: 18px; margin-bottom: 12px;
    }
    .monto-deuda { color: #E11D48; font-size: 1.2rem; font-weight: 800; }
    .monto-ok { color: #10B981; font-size: 1.2rem; font-weight: 800; }
    .tag { padding: 3px 8px; border-radius: 5px; font-size: 0.75rem; font-weight: 700; margin-right: 5px; }
    .tag-vend { background: #EEF2FF; color: #4338CA; }
    .tag-corp { background: #1E293B; color: white; }
    .tag-fact { background: #FEF3C7; color: #92400E; }
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
        
        # Blindaje de 9 columnas
        cols = ['Fecha', 'Nro_Ppto', 'Cliente', 'Monto_Total', 'Anticipo', 'Vendedor', 'Facturado', 'Fecha_Confirmacion', 'Corporativa']
        for c in cols:
            if c not in df.columns: df[c] = ""
            
        df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
        df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
        df['Saldo'] = df['Monto_Total'] - df['Anticipo']
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df['Fecha_Confirmacion'] = pd.to_datetime(df['Fecha_Confirmacion'], errors='coerce')
        
        # Clasificación para Gráficos
        df['Es_Corp'] = df['Corporativa'].apply(lambda x: str(x).upper() == "SI")
        df['Origen'] = df.apply(lambda r: "CORPORATIVO" if r['Es_Corp'] else r['Vendedor'], axis=1)
        
        # Antigüedad
        hoy = pd.Timestamp(datetime.now().date())
        df['Dias'] = (hoy - df['Fecha']).dt.days.fillna(0).astype(int)
        return df, ws
    except: return pd.DataFrame(), None

# --- 3. DASHBOARD ---
df, ws = obtener_datos()

if not df.empty:
    st.title("📊 Magallan Enterprise - Dashboard de Alto Rendimiento")

    # Sidebar
    with st.sidebar:
        st.header("Configuración")
        sel_mes = st.multiselect("Meses", options=list(range(1,13)), default=list(range(1,13)), format_func=lambda x: datetime(2000, x, 1).strftime('%B'))
        df_view = df[df['Fecha'].dt.month.isin(sel_mes)] if not df['Fecha'].isnull().all() else df

    # Métricas Superiores
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("VENTAS TOTALES", f"${df_view['Monto_Total'].sum():,.0f}")
    m2.metric("COBRADO", f"${df_view['Anticipo'].sum():,.0f}")
    m3.metric("PENDIENTE", f"${df_view['Saldo'].sum():,.0f}", delta_color="inverse")
    m4.metric("CORP. / EQUIPO", f"${df_view[df_view['Es_Corp']]['Monto_Total'].sum():,.0f} / ${df_view[~df_view['Es_Corp']]['Monto_Total'].sum():,.0f}")

    # --- GRÁFICOS COMPLETOS ---
    st.subheader("📈 Análisis de Gestión y Ventas")
    g1, g2, g3 = st.columns([1.2, 1, 1])

    with g1:
        # Cobranza por Origen (Corporativo vs Vendedores)
        rend = df_view.groupby('Origen').agg({'Anticipo':'sum', 'Saldo':'sum'}).reset_index()
        fig_cob = px.bar(rend, x='Origen', y=['Anticipo', 'Saldo'], title="Cobranza: Equipo vs Corporativo", 
                         barmode='group', color_discrete_map={'Anticipo':'#10B981', 'Saldo':'#E11D48'})
        st.plotly_chart(fig_cob, use_container_width=True)

    with g2:
        # Distribución de Facturación
        fig_fac = px.pie(df_view, values='Monto_Total', names='Facturado', title="Perfil de Facturación",
                         hole=0.4, color_discrete_sequence=['#0284C7', '#94A3B8'])
        st.plotly_chart(fig_fac, use_container_width=True)

    with g3:
        # Deuda Crítica (+30 días)
        df_view['Estado'] = df_view.apply(lambda r: 'Saldado' if r['Saldo']<=0 else ('Crítica (+30d)' if r['Dias']>30 else 'Reciente'), axis=1)
        fig_deu = px.pie(df_view[df_view['Saldo']>0], values='Saldo', names='Estado', title="Salud de la Deuda",
                         color='Estado', color_discrete_map={'Crítica (+30d)':'#E11D48', 'Reciente':'#F59E0B'})
        st.plotly_chart(fig_deu, use_container_width=True)

    st.divider()

    # --- CARGA Y LISTADO ---
    c_form, c_list = st.columns([1, 2.2])

    with c_form:
        st.subheader("➕ Nueva Entrada")
        with st.form("form_final", clear_on_submit=True):
            f_nro = st.text_input("Nro MAG#")
            f_cli = st.text_input("Cliente")
            f_ven = st.selectbox("Vendedor", ["Jonathan", "Jacqueline", "Roberto"])
            f_corp = st.checkbox("🏢 CUENTA CORPORATIVA")
            f_tot = st.number_input("Monto Total ($)", min_value=0.0)
            f_ant = st.number_input("Anticipo ($)", min_value=0.0)
            f_fac = st.selectbox("Facturación", ["Sin Facturar", "Facturado"])
            f_fec = st.date_input("Fecha Ppto", datetime.now())
            
            if st.form_submit_button("REGISTRAR"):
                f_conf = datetime.now().strftime("%Y-%m-%d")
                ws.append_row([f_fec.strftime("%Y-%m-%d"), f_nro, f_cli, f_tot, f_ant, f_ven, f_fac, f_conf, "SI" if f_corp else "NO"])
                st.success("Guardado!")
                st.rerun()

    with c_list:
        st.subheader("📋 Gestión de Cuentas")
        busc = st.text_input("🔍 Buscar cliente...")
        df_final = df_view[df_view.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df_view
        
        for i, r in df_final.sort_values(by='Fecha', ascending=False).iterrows():
            # Selección de Estilo
            estilo = "card-corp" if r['Es_Corp'] else "card-vendedor"
            tag_v = "CORPORATIVO" if r['Es_Corp'] else f"VEND: {r['Vendedor']}"
            tag_v_class = "tag-corp" if r['Es_Corp'] else "tag-vend"
            
            st.markdown(f"""
                <div class="{estilo}">
                    <div style="display:flex; justify-content:space-between;">
                        <div>
                            <span style="font-size:0.8rem; color:#64748B;">Ppto: {r['Fecha'].strftime('%d/%m/%y')} | Conf: {r['Fecha_Confirmacion'].strftime('%d/%m/%y')}</span><br>
                            <b>MAG-{r['Nro_Ppto']} | {r['Cliente']}</b><br>
                            <span class="tag {tag_v_class}">{tag_v}</span>
                            <span class="tag tag-fact">{r['Facturado']}</span>
                            <span style="font-size:0.75rem; color:#64748B;">🕒 {r['Dias']} días</span>
                        </div>
                        <div class="{'monto-ok' if r['Saldo']<=0 else 'monto-deuda'}">
                            {'$' + str(f"{r['Saldo']:,.0f}") if r['Saldo']>0 else 'SALDADO'}
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Modificar"):
                nt = st.number_input("Total", value=float(r['Monto_Total']), key=f"t{i}")
                na = st.number_input("Anticipo", value=float(r['Anticipo']), key=f"a{i}")
                if st.button("Guardar", key=f"b{i}"):
                    ws.update_cell(i+2, 4, nt)
                    ws.update_cell(i+2, 5, na)
                    st.rerun()