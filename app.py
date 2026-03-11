import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import plotly.express as px

# 1. CONFIGURACIÓN Y ESTILO PROFESIONAL
st.set_page_config(page_title="Grupo Magallan | Sistema Integral", layout="wide")

st.markdown("""
    <style>
    html, body, [class*="st-"] { font-size: 1.05rem !important; }
    .stButton>button { width: 100%; height: 50px; border-radius: 10px; background-color: #1E3A8A; color: white; }
    .chat-box { background-color: #F3F4F6; padding: 10px; border-radius: 10px; margin-bottom: 5px; border-left: 5px solid #1E3A8A; }
    .metric-card { background-color: #EFF6FF; padding: 15px; border-radius: 10px; border: 1px solid #DBEAFE; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# 2. CONEXIÓN Y CARGA (Sincronizado con tus pestañas reales)
@st.cache_resource
def conectar():
    return gspread.authorize(Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    ))

def cargar_datos(pestaña):
    try:
        sh = conectar().open("Gestion_Magallan")
        df = pd.DataFrame(sh.worksheet(pestaña).get_all_records())
        return df
    except:
        return pd.DataFrame()

# 3. SISTEMA DE ACCESO
if "authenticated" not in st.session_state:
    st.title("🏗️ Grupo Magallan | Acceso")
    u = st.selectbox("Usuario", ["---"] + list(st.secrets["usuarios"].keys()))
    p = st.text_input("Contraseña", type="password")
    if st.button("INGRESAR"):
        if u != "---" and str(st.secrets["usuarios"][u]).strip() == p.strip():
            st.session_state.update({"authenticated": True, "user": u})
            st.rerun()
else:
    # --- MENÚ LATERAL ---
    st.sidebar.title(f"👤 {st.session_state['user']}")
    opcion = st.sidebar.radio("MENÚ PRINCIPAL", ["📊 TABLERO", "🆕 NUEVO PPTO", "🚚 LOGÍSTICA", "💬 CHAT", "📈 RENDIMIENTO"])
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["authenticated"]
        st.rerun()

    # --- 1. TABLERO CON BUSCADOR DINÁMICO ---
    if opcion == "📊 TABLERO":
        st.title("📊 Control de Planta")
        df_p = cargar_datos("Proyectos")
        
        if not df_p.empty:
            # Buscador integrado
            busqueda = st.text_input("🔍 Buscar por Cliente o Nro_Ppto:", placeholder="Ej: Jonathan o 1001")
            
            # Filtro lógico
            if busqueda:
                df_mostrar = df_p[
                    df_p['Cliente'].astype(str).str.contains(busqueda, case=False) | 
                    df_p['Nro_Ppto'].astype(str).str.contains(busqueda, case=False)
                ]
            else:
                df_mostrar = df_p

            st.markdown(f'<div class="metric-card"><h3>Obras Visibles: {len(df_mostrar)}</h3></div>', unsafe_allow_html=True)
            st.divider()
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
        else:
            st.warning("No hay datos en 'Proyectos'.")

    # --- 2. NUEVO PPTO (SEGÚN TU ESTRUCTURA) ---
    elif opcion == "🆕 NUEVO PPTO":
        st.title("🆕 Carga de Proyecto")
        with st.form("form_carga"):
            c1, c2, c3 = st.columns(3)
            nro = c1.text_input("Nro_Ppto")
            cliente = c2.text_input("Cliente")
            monto = c3.number_input("Monto_Total_Ars", min_value=0)
            
            c4, c5, c6 = st.columns(3)
            estado = c4.selectbox("Estado_Fabricacion", ["Esperando", "Preparacion", "Terminado", "Entregado"])
            fecha_e = c5.date_input("Fecha_Entrega")
            iva = c6.selectbox("IVA", ["sin iva", "iva 10.5%", "iva 21%"])
            
            notas = st.text_area("Materiales_Pendientes")
            
            if st.form_submit_button("REGISTRAR"):
                sh = conectar().open("Gestion_Magallan")
                # Coincide con: Nro_Ppto, Cliente, Estado_Fabricacion, Fecha_Carga, Fecha_Entrega, Monto_Total_Ars, Pagado_Ars, IVA, Notas_Planta, Materiales_Pendientes
                nueva_fila = [nro, cliente, estado, datetime.now().strftime("%d/%m/%Y"), fecha_e.strftime("%d/%m/%Y"), monto, 0, iva, "", notas]
                sh.worksheet("Proyectos").append_row(nueva_fila)
                sh.worksheet("Historial").append_row([nro, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state['user'], "Alta de cortina"])
                st.success("✅ Guardado.")
                st.cache_data.clear()

    # --- 3. LOGÍSTICA (INSTALADORES) ---
    elif opcion == "🚚 LOGÍSTICA":
        st.title("🚚 Instalaciones")
        df_l = cargar_datos("Logistica")
        if not df_l.empty:
            st.dataframe(df_l, use_container_width=True, hide_index=True)
            with st.expander("➕ Cargar Movimiento de Logística"):
                with st.form("f_log"):
                    nro_l = st.text_input("Nro_Ppto")
                    tec = st.selectbox("Tecnicos", ["Irving", "Equipo A", "Equipo B"])
                    f_inst = st.date_input("Fecha_Instalacion")
                    est_ent = st.selectbox("Estado_Entrega", ["Pendiente", "Esperando", "Terminado"])
                    if st.form_submit_button("GUARDAR LOGÍSTICA"):
                        conectar().open("Gestion_Magallan").worksheet("Logistica").append_row([nro_l, tec, f_inst.strftime("%d/%m/%Y"), est_ent])
                        st.cache_data.clear()
                        st.rerun()

    # --- 4. CHAT INTERNO (POR PPTO) ---
    elif opcion == "💬 CHAT":
        st.title("💬 Chat de Equipo")
        df_c = cargar_datos("Chat_Interno")
        with st.form("chat_f", clear_on_submit=True):
            nro_p = st.text_input("Nro_Ppto")
            msg = st.text_input("Mensaje:")
            if st.form_submit_button("Enviar"):
                if msg:
                    # Captura: Nro_Ppto, Usuario, Fecha_Hora, Mensaje
                    conectar().open("Gestion_Magallan").worksheet("Chat_Interno").append_row([nro_p, st.session_state['user'], datetime.now().strftime("%d/%m/%Y %H:%M"), msg])
                    st.cache_data.clear()
                    st.rerun()
        if not df_c.empty:
            for _, r in df_c.iloc[::-1].iterrows():
                st.markdown(f"<div class='chat-box'><small>{r['Fecha_Hora']} - {r['Usuario']} (Ppto: {r['Nro_Ppto']})</small><br>{r['Mensaje']}</div>", unsafe_allow_html=True)

    # --- 5. RENDIMIENTO (ESTADÍSTICAS SIN ERRORES) ---
    elif opcion == "📈 RENDIMIENTO":
        st.title("📈 Análisis de Equipo")
        df_h = cargar_datos("Historial")
        if not df_h.empty:
            # Corrección de TypeError en fechas
            df_h['f_dt'] = pd.to_datetime(df_h['Fecha_Hora'], dayfirst=True, errors='coerce').dt.date
            c1, c2 = st.columns(2)
            f_ini = c1.date_input("Desde", value=date(2024, 1, 1))
            f_fin = c2.date_input("Hasta", value=date.today())
            df_f = df_h[(df_h['f_dt'] >= f_ini) & (df_h['f_dt'] <= f_fin)].dropna(subset=['f_dt'])
            if not df_f.empty:
                st.plotly_chart(px.pie(df_f, names='Usuario', hole=0.3))
                st.table(df_f['Usuario'].value_counts())