import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import plotly.express as px

# 1. ESTILO DE ALTA VISIBILIDAD (LETRA GIGANTE EN TODO EL SISTEMA)
st.set_page_config(page_title="Magallan Pro", layout="wide")

st.markdown("""
    <style>
    /* Letra grande para el cuerpo y el panel lateral */
    html, body, [class*="st-"], .st-emotion-cache-16idsys p {
        font-size: 1.6rem !important;
    }
    /* Títulos de menús laterales */
    .st-emotion-cache-16idsys { font-size: 1.7rem !important; }
    /* Botones de acción gigantes */
    .stButton>button {
        width: 100%;
        height: 90px;
        font-size: 2.2rem !important;
        background-color: #1E3A8A !important;
        color: white !important;
        border-radius: 15px;
        margin-top: 15px;
    }
    /* Etiquetas de campos */
    label { font-size: 1.9rem !important; font-weight: bold !important; color: #1E3A8A !important; }
    /* Tarjetas de alertas de atraso */
    .card-atraso { 
        background-color: #FEF2F2; 
        border-left: 20px solid #EF4444; 
        padding: 30px; 
        border-radius: 15px; 
        color: #991B1B; 
        font-weight: bold;
        margin-bottom: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. LOGIN CON SELECCIÓN DE USUARIO (SOLO CONTRASEÑA)
def check_auth():
    if "authenticated" not in st.session_state:
        st.title("🏗️ Grupo Magallan | Acceso")
        try:
            usuarios_dict = st.secrets["usuarios"]
            nombres = list(usuarios_dict.keys())
            
            u = st.selectbox("👤 Seleccione su Usuario", ["---"] + nombres)
            p = st.text_input("🔑 Contraseña", type="password")
            
            if st.button("INGRESAR AL SISTEMA"):
                if u != "---" and str(usuarios_dict[u]) == p:
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = u
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
        except:
            st.error("Error: Configure los usuarios en 'Secrets' de Streamlit")
        return False
    return True

# 3. CONEXIÓN SEGURA (ANTI-ERROR 502/429)
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
        def procesar(nombre_hoja):
            data = sh.worksheet(nombre_hoja).get_all_records()
            df = pd.DataFrame(data).astype(str)
            df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
            return df
        return procesar("Proyectos"), procesar("Historial"), datetime.now().strftime("%H:%M")
    except:
        return pd.DataFrame(), pd.DataFrame(), "Error de Conexión"

if check_auth():
    df_p, df_h, h_sincro = cargar_datos()

    # --- BARRA LATERAL ---
    st.sidebar.markdown(f"# 👤 {st.session_state['user']}")
    st.sidebar.write(f"Sincronizado: {h_sincro}")
    
    opcion = st.sidebar.radio("MENÚ:", ["📊 TABLERO", "📈 ESTADÍSTICAS", "📝 GESTIÓN"])
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["authenticated"]
        st.rerun()

    # --- TABLERO (ALERTAS VISIBLES) ---
    if opcion == "📊 TABLERO":
        st.title("📊 Control de Planta")
        if not df_p.empty:
            # Conversión segura de fechas para evitar errores de comparación
            df_p['f_limpia'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
            atrasos = df_p[(df_p['f_limpia'] < date.today()) & (df_p['estado_fabricacion'].str.lower() != "entregado")]
            
            if not atrasos.empty:
                st.subheader(f"🚨 Obras Atrasadas ({len(atrasos)})")
                for _, r in atrasos.iterrows():
                    st.markdown(f"<div class='card-atraso'>⚠️ CLIENTE: {r['cliente']} (#{r.get('nro_ppto', 'S/N')}) - VENCIMIENTO: {r['fecha_entrega']}</div>", unsafe_allow_html=True)
            
            st.divider()
            st.dataframe(df_p[['nro_ppto', 'cliente', 'estado_fabricacion', 'fecha_entrega']], use_container_width=True)

    # --- ESTADÍSTICAS (FILTRO DE FECHA CORREGIDO) ---
    elif opcion == "📈 ESTADÍSTICAS":
        st.title("📈 Rendimiento de Equipo")
        if not df_h.empty:
            # Solución definitiva al TypeError
            df_h['f_dt'] = pd.to_datetime(df_h['fecha_hora'], dayfirst=True, errors='coerce').dt.date
            
            c1, c2 = st.columns(2)
            f_inicio = c1.date_input("Desde:", value=date(2024, 1, 1))
            f_fin = c2.date_input("Hasta:", value=date.today())
            
            # Filtrado seguro entre objetos tipo date
            df_f = df_h[(df_h['f_dt'] >= f_inicio) & (df_h['f_dt'] <= f_fin)].dropna(subset=['f_dt'])
            
            if not df_f.empty:
                fig = px.pie(df_f, names='usuario', title="Movimientos por Operador", hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
                st.subheader("Resumen de Actividad")
                st.table(df_f['usuario'].value_counts())
            else:
                st.info("No hay datos registrados en este periodo.")

    # --- GESTIÓN (BUSCADOR POR NOMBRE AGREGADO) ---
    elif opcion == "📝 GESTIÓN":
        st.title("📝 Registrar Avance")
        if not df_p.empty:
            # Buscador de texto para facilitar encontrar clientes
            busqueda = st.text_input("🔍 Buscar por Nombre de Cliente o Presupuesto:").lower()
            
            # Filtro dinámico de la lista
            df_p['ref'] = df_p['nro_ppto'].astype(str) + " - " + df_p['cliente'].astype(str)
            opciones_filtradas = [o for o in df_p['ref'].unique() if busqueda in o.lower()]
            
            seleccion = st.selectbox("Seleccione la Obra para actualizar:", ["---"] + opciones_filtradas)
            
            if seleccion != "---":
                id_obra = seleccion.split(" - ")[0]
                with st.form("form_update"):
                    st.write(f"### Obra seleccionada: {seleccion}")
                    nuevo_estado = st.selectbox("Nuevo Estado:", ["Esperando", "Preparacion", "Terminado", "Entregado"])
                    
                    if st.form_submit_button("GUARDAR CAMBIO"):
                        sh = conectar().open("Gestion_Magallan")
                        # Buscamos la fila exacta en el Excel
                        fila = df_p[df_p['nro_ppto'] == id_obra].index[0] + 2
                        sh.worksheet("Proyectos").update_cell(fila, 3, nuevo_estado)
                        
                        # Registro en Historial para estadísticas
                        sh.worksheet("Historial").append_row([
                            id_obra, 
                            datetime.now().strftime("%d/%m/%Y %H:%M"), 
                            st.session_state['user'], 
                            f"Cambio a {nuevo_estado}"
                        ])
                        
                        st.cache_data.clear()
                        st.success("✅ ¡Estado actualizado correctamente!")
                        st.rerun()