import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import plotly.express as px
from fpdf import FPDF

# 1. CONFIGURACIÓN VISUAL (LETRA GRANDE Y CÓMODA)
st.set_page_config(page_title="Magallan Pro", layout="wide")
st.markdown("""
    <style>
    /* Letra general más grande */
    html, body, [class*="st-"] { font-size: 1.4rem !important; }
    /* Títulos y etiquetas de botones gigantes */
    label { font-size: 1.8rem !important; font-weight: bold !important; color: #1E3A8A !important; }
    .stButton>button { width: 100%; height: 90px; font-size: 2.2rem !important; background-color: #1E3A8A !important; color: white !important; border-radius: 15px; }
    /* Estilo de tarjetas de alerta */
    .card-atraso { background-color: #FEF2F2; border-left: 15px solid #EF4444; padding: 25px; border-radius: 15px; color: #991B1B; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 2. LOGIN SIMPLIFICADO (SELECCIONAR USUARIO)
def check_password():
    if "auth" not in st.session_state:
        st.title("🏗️ Grupo Magallan | Acceso")
        usuarios_dict = st.secrets["usuarios"]
        lista_usuarios = list(usuarios_dict.keys())
        
        # Usuario seleccionable para mayor comodidad
        u = st.selectbox("Seleccione su Nombre", ["---"] + lista_usuarios)
        p = st.text_input("Ingrese su Contraseña", type="password")
        
        if st.button("INGRESAR AL SISTEMA"):
            if u != "---" and str(usuarios_dict[u]) == p:
                st.session_state["auth"] = True
                st.session_state["user"] = u
                st.rerun()
            else:
                st.error("Credenciales incorrectas o usuario no seleccionado")
        return False
    return True

# 3. CARGA DE DATOS CON PROTECCIÓN ANTI-ERRORES (429/502)
@st.cache_resource
def conectar_gsheets():
    return gspread.authorize(Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    ))

@st.cache_data(ttl=300)
def cargar_datos():
    try:
        sh = conectar_gsheets().open("Gestion_Magallan")
        def limpiar(hoja):
            data = sh.worksheet(hoja).get_all_records()
            df = pd.DataFrame(data).astype(str)
            df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
            return df
        return limpiar("Proyectos"), limpiar("Historial"), datetime.now().strftime("%H:%M")
    except Exception as e:
        st.warning("⚠️ Error de conexión temporal. Reintentando...")
        return pd.DataFrame(), pd.DataFrame(), "Error"

if check_password():
    df_p, df_h, ultima_act = cargar_datos()

    # --- NAVEGACIÓN LATERAL ---
    st.sidebar.title(f"👤 {st.session_state['user']}")
    menu = st.sidebar.radio("IR A:", ["📊 TABLERO", "📈 ESTADÍSTICAS", "📝 GESTIÓN"])
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["auth"]
        st.rerun()

    # --- TABLERO (VISIBILIDAD TOTAL) ---
    if menu == "📊 TABLERO":
        st.title("📊 Control de Planta")
        if not df_p.empty:
            # Corrección de fecha para evitar TypeError
            df_p['f_entrega'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
            atrasos = df_p[(df_p['f_entrega'] < date.today()) & (df_p['estado_fabricacion'].str.lower() != "entregado")]
            
            if not atrasos.empty:
                st.subheader(f"🚨 Alertas de Entrega ({len(atrasos)})")
                for _, r in atrasos.iterrows():
                    st.markdown(f"<div class='card-atraso'>Obra: {r['cliente']} (#{r.get('nro_ppto', 'S/N')}) - Venció: {r['fecha_entrega']}</div>", unsafe_allow_html=True)
            
            st.divider()
            st.dataframe(df_p[['nro_ppto', 'cliente', 'estado_fabricacion', 'fecha_entrega']], use_container_width=True)

    # --- ESTADÍSTICAS CON FILTRO PROTEGIDO ---
    elif menu == "📈 ESTADÍSTICAS":
        st.title("📈 Análisis de Rendimiento")
        if not df_h.empty:
            # Convertimos fechas a formato date de Python para que la comparación sea válida
            df_h['f_dt'] = pd.to_datetime(df_h['fecha_hora'], dayfirst=True, errors='coerce').dt.date
            
            col_f1, col_f2 = st.columns(2)
            f_ini = col_f1.date_input("Desde:", value=date(2024, 1, 1))
            f_fin = col_f2.date_input("Hasta:", value=date.today())
            
            # Filtro seguro entre objetos 'date'
            df_filtrado = df_h[(df_h['f_dt'] >= f_ini) & (df_h['f_dt'] <= f_fin)].dropna(subset=['f_dt'])
            
            if not df_filtrado.empty:
                c1, c2 = st.columns(2)
                fig1 = px.pie(df_filtrado, names='usuario', title="Actividad por Operario")
                c1.plotly_chart(fig1, use_container_width=True)
                
                fig2 = px.histogram(df_filtrado, x='f_dt', title="Movimientos por Día")
                c2.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No hay registros en el rango seleccionado.")

    # --- GESTIÓN (ACTUALIZAR EXCEL) ---
    elif menu == "📝 GESTIÓN":
        st.title("📝 Registro de Cambios")
        if not df_p.empty:
            # Creamos la columna búsqueda asegurando que exista nro_ppto
            df_p['busq'] = df_p['nro_ppto'].astype(str) + " - " + df_p['cliente'].astype(str)
            sel = st.selectbox("Seleccione la Obra:", ["---"] + list(df_p['busq'].unique()))
            
            if sel != "---":
                id_obra = sel.split(" - ")[0]
                with st.form("form_gestion"):
                    nuevo = st.selectbox("Nuevo Estado:", ["Esperando", "Preparacion", "Terminado", "Entregado"])
                    if st.form_submit_button("GUARDAR CAMBIO"):
                        sh = conectar_gsheets().open("Gestion_Magallan")
                        fila = df_p[df_p['nro_ppto'] == id_obra].index[0] + 2
                        sh.worksheet("Proyectos").update_cell(fila, 3, nuevo)
                        sh.worksheet("Historial").append_row([
                            id_obra, datetime.now().strftime("%d/%m/%Y %H:%M"), 
                            st.session_state['user'], f"Cambio a {nuevo}"
                        ])
                        st.cache_data.clear()
                        st.success("¡Cambio guardado!")
                        st.rerun()