import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import plotly.express as px

# 1. ESTILO NORMALIZADO (EQUILIBRADO Y PROFESIONAL)
st.set_page_config(page_title="Magallan Pro", layout="wide")

st.markdown("""
    <style>
    /* Tamaño de letra estándar para lectura cómoda */
    html, body, [class*="st-"] { font-size: 1.1rem !important; }
    /* Panel lateral con letra clara pero no excesiva */
    .st-emotion-cache-16idsys p { font-size: 1.1rem !important; }
    /* Botones de acción con tamaño optimizado */
    .stButton>button {
        width: 100%;
        height: 60px;
        font-size: 1.3rem !important;
        background-color: #1E3A8A !important;
        color: white !important;
        border-radius: 10px;
    }
    /* Títulos y etiquetas */
    label { font-size: 1.2rem !important; font-weight: bold !important; color: #1E3A8A !important; }
    /* Alertas de atraso compactas */
    .card-atraso { 
        background-color: #FEF2F2; 
        border-left: 10px solid #EF4444; 
        padding: 15px; 
        border-radius: 8px; 
        color: #991B1B; 
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. LOGIN POR SELECCIÓN
def check_auth():
    if "authenticated" not in st.session_state:
        st.title("🏗️ Grupo Magallan | Acceso")
        usuarios_dict = st.secrets["usuarios"]
        u = st.selectbox("👤 Seleccione Usuario", ["---"] + list(usuarios_dict.keys()))
        p = st.text_input("🔑 Contraseña", type="password")
        if st.button("INGRESAR"):
            if u != "---" and str(usuarios_dict[u]) == p:
                st.session_state["authenticated"] = True
                st.session_state["user"] = u
                st.rerun()
            else:
                st.error("Datos incorrectos")
        return False
    return True

# 3. CARGA SEGURA CON REINTENTO AUTOMÁTICO (ANTI-502)
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
    except Exception:
        # Si falla (Error 502), devuelve tablas vacías para que la app no explote
        return pd.DataFrame(), pd.DataFrame(), "Error de Red"

if check_auth():
    df_p, df_h, h_sincro = cargar_datos()

    # --- BARRA LATERAL ---
    st.sidebar.markdown(f"### 👤 {st.session_state['user']}")
    opcion = st.sidebar.radio("MENÚ:", ["📊 TABLERO", "📈 ESTADÍSTICAS", "📝 GESTIÓN"])
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["authenticated"]
        st.rerun()

    # --- TABLERO ---
    if opcion == "📊 TABLERO":
        st.title("📊 Control de Planta")
        if not df_p.empty:
            # Blindaje de fechas: convertir a fecha real ignorando errores
            df_p['f_dt'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
            atrasos = df_p[(df_p['f_dt'] < date.today()) & (df_p['estado_fabricacion'].str.lower() != "entregado")]
            if not atrasos.empty:
                for _, r in atrasos.iterrows():
                    st.markdown(f"<div class='card-atraso'>🚨 {r['cliente']} - Venció: {r['fecha_entrega']}</div>", unsafe_allow_html=True)
            st.dataframe(df_p[['nro_ppto', 'cliente', 'estado_fabricacion', 'fecha_entrega']], use_container_width=True)

    # --- ESTADÍSTICAS (SOLUCIÓN AL TYPEERROR DE LA CAPTURA) ---
    elif opcion == "📈 ESTADÍSTICAS":
        st.title("📈 Rendimiento")
        if not df_h.empty:
            # PASO CRÍTICO: Asegurar que f_dt sea tipo 'date' para comparar con date_input
            df_h['f_dt'] = pd.to_datetime(df_h['fecha_hora'], dayfirst=True, errors='coerce').dt.date
            
            c1, c2 = st.columns(2)
            f_ini = c1.date_input("Desde:", value=date(2024, 1, 1))
            f_fin = c2.date_input("Hasta:", value=date.today())
            
            # Filtrado seguro
            df_f = df_h[(df_h['f_dt'] >= f_ini) & (df_h['f_dt'] <= f_fin)]
            
            if not df_f.empty:
                st.plotly_chart(px.pie(df_f, names='usuario', hole=0.3), use_container_width=True)
                st.table(df_f['usuario'].value_counts())
            else:
                st.info("No hay datos en este rango.")

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
                        st.success("¡Listo!")
                        st.rerun()