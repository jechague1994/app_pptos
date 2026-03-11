import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import plotly.express as px
from fpdf import FPDF

# 1. CONFIGURACIÓN DE PÁGINA Y SEGURIDAD (VÍA SECRETS)
st.set_page_config(page_title="Magallan | Gestión Pro", layout="wide")

def check_password():
    if "auth" not in st.session_state:
        st.title("🏗️ Control de Planta - Grupo Magallan")
        # Leemos los usuarios desde st.secrets["usuarios"]
        usuarios_dict = st.secrets["usuarios"]
        
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar"):
            if u in usuarios_dict and str(usuarios_dict[u]) == p:
                st.session_state["auth"] = True
                st.session_state["user"] = u
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
        return False
    return True

# 2. GENERADOR DE REPORTES PDF
def generar_pdf_reporte(df, operador):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE DE ACTIVIDAD - GRUPO MAGALLAN", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(190, 10, f"Generado por: {operador} | Fecha: {date.today()}", ln=True, align='C')
    pdf.ln(10)
    
    # Encabezados
    pdf.set_fill_color(30, 58, 138) # Azul Magallan
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 10, "Presupuesto", 1, 0, 'C', True)
    pdf.cell(50, 10, "Fecha/Hora", 1, 0, 'C', True)
    pdf.cell(40, 10, "Usuario", 1, 0, 'C', True)
    pdf.cell(70, 10, "Acción Realizada", 1, 1, 'C', True)
    
    # Datos
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=9)
    for _, row in df.iterrows():
        pdf.cell(30, 10, str(row['nro_ppto']), 1)
        pdf.cell(50, 10, str(row['fecha_hora']), 1)
        pdf.cell(40, 10, str(row['usuario']), 1)
        pdf.cell(70, 10, str(row['accion']), 1)
        pdf.ln(0)
    
    return pdf.output(dest='S').encode('latin-1')

if check_password():
    # 3. ESTILOS INDUSTRIALES
    st.markdown("""
        <style>
        .stButton>button { width: 100%; height: 80px; font-size: 1.8rem !important; background-color: #1E3A8A !important; color: white !important; border-radius: 15px; }
        .card-atraso { background-color: #FEF2F2; border-left: 15px solid #EF4444; padding: 25px; border-radius: 15px; color: #991B1B; font-weight: bold; }
        .stMetric { background-color: #F8FAFC; padding: 15px; border-radius: 10px; border: 1px solid #E2E8F0; }
        </style>
        """, unsafe_allow_html=True)

    # 4. CONEXIÓN Y CARGA (BLINDAJE ANTI-ERRORES 429/502)
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
            def limpiar_hoja(nombre):
                # Convertimos todo a texto para evitar errores de tipo
                df = pd.DataFrame(sh.worksheet(nombre).get_all_records()).astype(str)
                df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
                return df
            return limpiar_hoja("Proyectos"), limpiar_hoja("Historial"), datetime.now().strftime("%H:%M")
        except:
            return pd.DataFrame(), pd.DataFrame(), "Error de Sincronización"

    df_p, df_h, ultima_act = cargar_datos()

    # --- BARRA LATERAL ---
    st.sidebar.title(f"👤 {st.session_state['user']}")
    st.sidebar.write(f"Sincronizado: {ultima_act}")
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["auth"]
        st.rerun()
    
    menu = st.sidebar.radio("MENÚ PRINCIPAL", ["📊 TABLERO", "📈 ESTADÍSTICAS", "📝 GESTIÓN"])

    # --- LÓGICA DE MENÚS ---
    if menu == "📊 TABLERO":
        st.title("📊 Control de Planta")
        # Alertas de Atraso
        df_p['f_entrega'] = pd.to_datetime(df_p['fecha_entrega'], errors='coerce').dt.date
        atrasos = df_p[(df_p['f_entrega'] < date.today()) & (df_p['estado_fabricacion'].str.lower() != "entregado")]
        
        if not atrasos.empty:
            st.subheader(f"🚨 Atrasos Detectados ({len(atrasos)})")
            for _, r in atrasos.iterrows():
                st.markdown(f"<div class='card-atraso'>⚠️ {r['cliente']} (#{r['nro_ppto']}) - Venció: {r['fecha_entrega']}</div>", unsafe_allow_html=True)
        
        st.divider()
        st.dataframe(df_p[['nro_ppto', 'cliente', 'estado_fabricacion', 'fecha_entrega']], use_container_width=True)

    elif menu == "📈 ESTADÍSTICAS":
        st.title("📈 Análisis de Rendimiento")
        if not df_h.empty:
            # Filtros de Fecha
            df_h['f_dt'] = pd.to_datetime(df_h['fecha_hora'], dayfirst=True, errors='coerce').dt.date
            col_f1, col_f2 = st.columns(2)
            f_ini = col_f1.date_input("Desde:", value=date(2024, 1, 1))
            f_fin = col_f2.date_input("Hasta:", value=date.today())
            
            df_filtrado = df_h[(df_h['f_dt'] >= f_ini) & (df_h['f_dt'] <= f_fin)]
            
            if not df_filtrado.empty:
                c1, c2 = st.columns(2)
                fig_pie = px.pie(df_filtrado, names='usuario', title="Acciones por Usuario")
                c1.plotly_chart(fig_pie, use_container_width=True)
                
                fig_hist = px.histogram(df_filtrado, x='f_dt', title="Movimientos por Día")
                c2.plotly_chart(fig_hist, use_container_width=True)
                
                # Descarga de PDF
                st.divider()
                reporte_pdf = generar_pdf_reporte(df_filtrado, st.session_state['user'])
                st.download_button("📄 Descargar Reporte PDF", data=reporte_pdf, file_name=f"Magallan_{f_ini}a{f_fin}.pdf")
            else:
                st.warning("No hay registros en esas fechas.")

    elif menu == "📝 GESTIÓN":
        st.title("📝 Editar Estados")
        df_p['busq'] = df_p['nro_ppto'] + " - " + df_p['cliente']
        sel_obra = st.selectbox("Seleccione Obra:", ["---"] + list(df_p['busq'].unique()))
        
        if sel_obra != "---":
            id_obra = sel_obra.split(" - ")[0]
            with st.form("form_edit"):
                nuevo_est = st.selectbox("Nuevo Estado:", ["Esperando", "Preparacion", "Terminado", "Entregado"])
                if st.form_submit_button("ACTUALIZAR"):
                    sh = conectar_gsheets().open("Gestion_Magallan")
                    fila = df_p[df_p['nro_ppto'] == id_obra].index[0] + 2
                    sh.worksheet("Proyectos").update_cell(fila, 3, nuevo_est)
                    # El historial permite la estadística
                    sh.worksheet("Historial").append_row([
                        id_obra, 
                        datetime.now().strftime("%d/%m/%Y %H:%M"), 
                        st.session_state['user'], 
                        f"Cambio a {nuevo_est}"
                    ])
                    st.cache_data.clear()
                    st.success("Cambio registrado exitosamente.")
                    st.rerun()