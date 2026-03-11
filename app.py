import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import plotly.express as px

# 1. CONFIGURACIÓN Y ESTILO NORMALIZADO
st.set_page_config(page_title="Magallan Pro", layout="wide")

st.markdown("""
    <style>
    html, body, [class*="st-"] { font-size: 1.1rem !important; }
    .st-emotion-cache-16idsys p { font-size: 1.1rem !important; }
    .stButton>button {
        width: 100%; height: 60px; font-size: 1.3rem !important;
        background-color: #1E3A8A !important; color: white !important; border-radius: 10px;
    }
    label { font-size: 1.2rem !important; font-weight: bold !important; color: #1E3A8A !important; }
    .card-atraso { 
        background-color: #FEF2F2; border-left: 10px solid #EF4444; 
        padding: 15px; border-radius: 8px; color: #991B1B; margin-bottom: 10px;
    }
    .metric-container {
        background-color: #F0F9FF; padding: 20px; border-radius: 15px;
        border: 1px solid #BAE6FD; text-align: center; margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. LOGIN (Clave jony051294 en Secrets)
def check_auth():
    if "authenticated" not in st.session_state:
        st.title("🏗️ Grupo Magallan | Acceso")
        try:
            usuarios_dict = st.secrets["usuarios"]
            nombres = [n.strip() for n in usuarios_dict.keys()]
            u = st.selectbox("👤 Seleccione Usuario", ["---"] + nombres)
            p = st.text_input("🔑 Contraseña", type="password")
            if st.button("INGRESAR"):
                if u != "---" and str(usuarios_dict[u]).strip() == p.strip():
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = u
                    st.rerun()
                else:
                    st.error("Datos incorrectos.")
        except:
            st.error("Error: Verifique los Secrets en Streamlit.")
        return False
    return True

# 3. CARGA DE DATOS PROTEGIDA (SOLUCIÓN 502)
@st.cache_resource
def conectar():
    return gspread.authorize(Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    ))

@st.cache_data(ttl=300)
def cargar_datos():
    try:
        sh = conectar().open("Gestion_Magallan")
        def proc(h):
            df = pd.DataFrame(sh.worksheet(h).get_all_records()).astype(str)
            df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
            return df
        return proc("Proyectos"), proc("Historial"), datetime.now().strftime("%H:%M")
    except:
        return pd.DataFrame(), pd.DataFrame(), "Error"

if check_auth():
    df_p, df_h, h_sincro = cargar_datos()

    # --- BARRA LATERAL ---
    st.sidebar.markdown(f"### 👤 {st.session_state['user']}")
    if st.sidebar.button("🔄 RECONECTAR SISTEMA"):
        st.cache_data.clear()
        st.rerun()
    opcion = st.sidebar.radio("IR A:", ["📊 TABLERO", "📈 ESTADÍSTICAS", "📝 GESTIÓN"])
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["authenticated"]
        st.rerun()

    # --- TABLERO (CON MÉTRICA DE PRODUCTIVIDAD) ---
    if opcion == "📊 TABLERO":
        st.title("📊 Control de Planta")
        
        if not df_p.empty and not df_h.empty:
            # Cálculo de eficiencia hoy
            hoy_str = date.today().strftime("%d/%m/%Y")
            df_h['f_dt_str'] = pd.to_datetime(df_h['fecha_hora'], dayfirst=True, errors='coerce').dt.strftime("%d/%m/%Y")
            terminados_hoy = len(df_h[(df_h['f_dt_str'] == hoy_str) & (df_h['detalle'].str.contains("Terminado|Entregado", case=False))])
            total_obras = len(df_p)
            porcentaje = (terminados_hoy / total_obras * 100) if total_obras > 0 else 0
            
            st.markdown(f"""
                <div class="metric-container">
                    <h2 style="margin:0; color:#0369A1;">🚀 Productividad de Hoy</h2>
                    <p style="font-size:2rem; font-weight:bold; margin:10px 0;">{terminados_hoy} Obras Finalizadas</p>
                    <p style="color:#0C4A6E;">Esto representa el {porcentaje:.1f}% de la carga total de planta.</p>
                </div>
            """, unsafe_allow_html=True)

        if h_sincro == "Error":
            st.error("⚠️ Error de conexión. Use 'RECONECTAR SISTEMA'.")
        elif not df_p.empty:
            df_p['f_dt'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
            atrasos = df_p[(df_p['f_dt'] < date.today()) & (df_p['estado_fabricacion'].str.lower() != "entregado")]
            for _, r in atrasos.iterrows():
                st.markdown(f"<div class='card-atraso'>🚨 {r['cliente']} - Venció: {r['fecha_entrega']}</div>", unsafe_allow_html=True)
            st.dataframe(df_p[['nro_ppto', 'cliente', 'estado_fabricacion', 'fecha_entrega']], use_container_width=True)

    # --- ESTADÍSTICAS (SIN TYPEERROR) ---
    elif opcion == "📈 ESTADÍSTICAS":
        st.title("📈 Análisis de Rendimiento")
        if not df_h.empty:
            df_h['f_dt'] = pd.to_datetime(df_h['fecha_hora'], dayfirst=True, errors='coerce').dt.date
            c1, c2 = st.columns(2)
            f_ini = c1.date_input("Desde:", value=date(2024, 1, 1))
            f_fin = c2.date_input("Hasta:", value=date.today())
            df_f = df_h[(df_h['f_dt'] >= f_ini) & (df_h['f_dt'] <= f_fin)].dropna(subset=['f_dt'])
            if not df_f.empty:
                st.plotly_chart(px.pie(df_f, names='usuario', hole=0.3), use_container_width=True)
                st.table(df_f['usuario'].value_counts())

    # --- GESTIÓN CON BUSCADOR ---
    elif opcion == "📝 GESTIÓN":
        st.title("📝 Actualizar Obra")
        if not df_p.empty:
            busq = st.text_input("🔍 Buscar Cliente/Presupuesto:").lower()
            df_p['ref'] = df_p['nro_ppto'] + " - " + df_p['cliente']
            lista = [o for o in df_p['ref'].unique() if busq in o.lower()]
            sel = st.selectbox("Obra:", ["---"] + lista)
            if sel != "---":
                id_o = sel.split(" - ")[0]
                with st.form("upd"):
                    nuevo = st.selectbox("Estado:", ["Esperando", "Preparacion", "Terminado", "Entregado"])
                    if st.form_submit_button("GUARDAR"):
                        sh = conectar().open("Gestion_Magallan")
                        fila = df_p[df_p['nro_ppto'] == id_o].index[0] + 2
                        sh.worksheet("Proyectos").update_cell(fila, 3, nuevo)
                        sh.worksheet("Historial").append_row([id_o, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state['user'], f"Cambio a {nuevo}"])
                        st.cache_data.clear()
                        st.success("¡Guardado!")
                        st.rerun()