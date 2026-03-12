import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
from fpdf import FPDF
import plotly.express as px

# URL del logo oficial de Grupo Magallan
LOGO_URL = "https://r.jina.ai/i/0586f37648354c4193568c07d3967484"

# 1. CONFIGURACIÓN DE INTERFAZ Y ESTILOS (JIRA + LOGO MOSAICO)
st.set_page_config(page_title="Magallan | Jira Enterprise", layout="wide")

st.markdown(f"""
    <style>
    /* Fondo con logo en mosaico sutil */
    .stApp {{ 
        background-color: #F4F5F7;
        background-image: url("{LOGO_URL}");
        background-repeat: repeat;
        background-size: 80px; /* Tamaño del mosaico */
        background-opacity: 0.03; /* Opacidad sutil */
        image-rendering: -webkit-optimize-contrast;
    }}
    
    /* Contenedor principal de la app */
    .block-container {{
        background-color: white;
        padding-top: 3rem !important;
        padding-bottom: 3rem !important;
        padding-left: 5rem !important;
        padding-right: 5rem !important;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-top: 2rem;
        margin-bottom: 2rem;
    }}

    /* Tarjetas de ticket estilo Jira */
    .ticket-card {{ 
        background-color: white; padding: 18px; border-radius: 8px; 
        border: 1px solid #DFE1E6; margin-bottom: 12px; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.03); font-family: sans-serif;
        cursor: pointer;
        transition: box-shadow 0.3s ease;
    }}
    .ticket-card:hover {{
        box-shadow: 0 4px 8px rgba(0,0,0,0.08);
    }}
    .status-terminado {{ border-left: 8px solid #36B37E; }}
    .status-atrasado {{ border-left: 8px solid #FF5630; }}
    .status-proceso {{ border-left: 8px solid #0052CC; }}
    .status-pagado {{ border-left: 8px solid #6554C0; background-color: #EAE6FF !important; }}
    
    /* Barra lateral estilo Jira */
    .sidebar-mag {{ background-color: #FAFBFC; padding: 20px; border-radius: 10px; border: 1px solid #DFE1E6; }}
    
    /* Saldo destacado */
    .saldo-destacado {{ background-color: #FFFAE6; color: #826a00; padding: 10px; border-radius: 8px; font-weight: bold; font-size: 1.1em; text-align: center; border: 1px solid #F5E6BF; }}
    
    /* Títulos estilo Jira */
    h1, h2, h3, h4 {{ color: #172B4D; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
    
    /* Botones principales estilo Jira (Azul Corporativo) */
    .stButton > button {{
        background-color: #0052CC !important;
        color: white !important;
        border-radius: 6px !important;
        padding: 10px 20px !important;
        font-weight: 600 !important;
        border: none !important;
    }}
    .stButton > button:hover {{
        background-color: #0065FF !important;
    }}
    </style>
    """, unsafe_allow_html=True)

# 2. GENERADOR DE PDF CORREGIDO (Solución al error AttributeError y Unicode)
def generar_pdf_seguro(tk):
    pdf = FPDF()
    pdf.add_page()
    try: pdf.image(LOGO_URL, x=10, y=8, w=50)
    except: 
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "GRUPO MAGALLAN", ln=True)
    
    pdf.ln(25)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=str(f"ORDEN DE TRABAJO: MAG-{tk['Nro_Ppto']}"), ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12)
    pdf.cell(100, 8, txt=str(f"Cliente: {tk['Cliente']}"))
    pdf.cell(100, 8, txt=str(f"Ubicación: {tk.get('Ubicacion', 'No informada')}"), ln=True)
    pdf.cell(100, 8, txt=str(f"Fecha Entrega: {tk['Fecha_Entrega']}"), ln=True)
    
    # Cálculos Financieros Seguros (Forzando conversión a int)
    total = int(pd.to_numeric(tk['Monto_Total_Ars'], errors='coerce') or 0)
    pagado = int(pd.to_numeric(tk.get('Pagado_Ars', 0), errors='coerce') or 0)
    saldo = total - pagado
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 8, txt=str(f"TOTAL: ${total}"))
    pdf.cell(100, 8, txt=str(f"SALDO A COBRAR: ${saldo}"), ln=True)
    
    pdf.ln(10)
    pdf.cell(0, 10, txt="Detalle de Materiales / Notas:", ln=True)
    pdf.set_font("Arial", size=11)
    # Reemplazo de saltos de línea para multi_cell
    notas_seguras = str(tk['Materiales_Pendientes']).replace('\n', ' ')
    pdf.multi_cell(0, 8, txt=notas_seguras)
    return pdf.output(dest='S').encode('latin-1', errors='replace') # errors='replace' para Unicode

# 3. CONEXIÓN A GOOGLE SHEETS
@st.cache_resource
def iniciar_conexion():
    return gspread.authorize(Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    ))

def traer_datos(nombre_hoja):
    try:
        sh = iniciar_conexion().open("Gestion_Magallan")
        ws = sh.worksheet(nombre_hoja)
        return pd.DataFrame(ws.get_all_records()), ws
    except: return pd.DataFrame(), None

# 4. SISTEMA DE LOGIN
if "authenticated" not in st.session_state:
    st.markdown("""
        <div style="display: flex; justify-content: center; align-items: center; height: 100vh;">
            <div style="background-color: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 400px; text-align: center;">
                <img src="LOGO_URL" width="150" style="margin-bottom: 20px;">
                <h3 style="margin-bottom: 30px; color: #172B4D;">Acceso Magallan Enterprise</h3>
    """, unsafe_allow_html=True)
    u = st.selectbox("Usuario", ["---"] + list(st.secrets["usuarios"].keys()))
    p = st.text_input("Contraseña", type="password")
    if st.button("ACCEDER AL SISTEMA", use_container_width=True):
        if u != "---" and str(st.secrets["usuarios"][u]).strip() == p.strip():
            st.session_state.update({"authenticated": True, "user": u})
            st.rerun()
    st.markdown("""
            </div>
        </div>
    """, unsafe_allow_html=True)
else:
    # MENÚ LATERAL ESTILO JIRA
    st.sidebar.image(LOGO_URL, use_container_width=True)
    st.sidebar.markdown(f"<p style='text-align: center; color: #6B778C; margin-top: -15px;'>🏗️ *{st.session_state['user']}*</p>", unsafe_allow_html=True)
    st.sidebar.markdown("---")
    nav = st.sidebar.radio("MENÚ PRINCIPAL", ["📋 Backlog de Planta", "📊 Reportes Semanales", "🆕 Crear Nuevo Ticket"])
    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar Sesión", use_container_width=True):
        del st.session_state["authenticated"]; st.rerun()

    # --- PANEL DE CONTROL ---
    if nav == "📋 Backlog de Planta":
        df, ws = traer_datos("Proyectos")
        st.title("📋 Backlog y Control de Planta")
        filtro = st.text_input("🔍 Buscar por Cliente o Localidad...", key="search_input")
        
        if not df.empty:
            st.markdown("---")
            for _, r in df.iterrows():
                # Búsqueda en nombre o ubicación
                if filtro.lower() in str(r['Cliente']).lower() or filtro.lower() in str(r.get('Ubicacion','')).lower():
                    # Lógica de Saldos y Colores (Manejo robusto de montos)
                    total = int(pd.to_numeric(r['Monto_Total_Ars'], errors='coerce') or 0)
                    pagado = int(pd.to_numeric(r.get('Pagado_Ars', 0), errors='coerce') or 0)
                    saldo = total - pagado
                    
                    try: vence = pd.to_datetime(r['Fecha_Entrega'], dayfirst=True).date() < date.today()
                    except: vence = False
                    
                    # Determinar color
                    if saldo <= 0: clase = "status-pagado"
                    elif str(r['Estado_Fabricacion']).lower() in ["terminado", "entregado"]: clase = "status-terminado"
                    elif vence: clase = "status-atrasado"
                    else: clase = "status-proceso"
                    
                    st.markdown(f"""
                        <div class='ticket-card {clase}' onclick='alert("Utilice el selector de abajo para detalles")'>
                            <b>MAG-{r['Nro_Ppto']}</b> | {r['Cliente']} | 📍 {r.get('Ubicacion', 'S/D')} | 
                            <b>Saldo: ${saldo}</b>
                        </div>
                        """, unsafe_allow_html=True)
            
            st.markdown("---")
            seleccion = st.selectbox("👉 Seleccione Obra para Detalle / PDF:", ["---"] + [f"{r['Nro_Ppto']} - {r['Cliente']}" for _, r in df.iterrows()])
            
            if seleccion != "---":
                ppto_id = str(seleccion.split(" - ")[0])
                tk = df[df['Nro_Ppto'].astype(str) == ppto_id].iloc[0]
                
                c_form, c_pdf = st.columns([2, 1])
                with c_form:
                    st.markdown("### Detalles del Presupuesto")
                    with st.form("edicion_segura"):
                        f_u = st.text_input("📍 Localidad / Ubicación", value=tk.get('Ubicacion', ''))
                        f_m = st.number_input("Monto Total ($)", value=int(pd.to_numeric(tk['Monto_Total_Ars'], errors='coerce') or 0))
                        f_p = st.number_input("Pagado ($)", value=int(pd.to_numeric(tk.get('Pagado_Ars', 0), errors='coerce') or 0))
                        f_i = st.selectbox("IVA", ["sin iva", "iva 21%"], index=0 if "sin" in str(tk['IVA']).lower() else 1)
                        f_n = st.text_area("📋 Notas Técnicas de Planta", value=str(tk['Materiales_Pendientes']))
                        
                        if st.form_submit_button("GUARDAR CAMBIOS EN TICKET"):
                            idx = df[df['Nro_Ppto'].astype(str) == ppto_id].index[0] + 2
                            ws.update_cell(idx, 6, f_m); ws.update_cell(idx, 7, f_p)
                            ws.update_cell(idx, 8, f_i); ws.update_cell(idx, 10, f_n); ws.update_cell(idx, 11, f_u)
                            traer_datos("Historial")[1].append_row([ppto_id, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state['user'], "Actualización Integral de Ticket"])
                            st.success("Ticket Actualizado Correctamente"); st.rerun()

                with c_pdf:
                    st.markdown("<div class='sidebar-mag'>", unsafe_allow_html=True)
                    st.markdown("### Estado y Acciones")
                    s_actual = f_m - f_p
                    if s_actual <= 0: 
                        st.markdown(f"<div class='saldo-destacado'>✅ TOTALMENTE PAGADO (Monto ${f_m})</div>", unsafe_allow_html=True)
                    else: 
                        st.markdown(f"<div class='saldo-destacado'>⚠️ PENDIENTE: ${s_actual}</div>", unsafe_allow_html=True)
                    st.markdown("---")
                    
                    # Generación de PDF con el logo oficial
                    st.download_button("📄 GENERAR ORDEN PDF (Logo)", data=generar_pdf_seguro(tk), file_name=f"MAG_{ppto_id}.pdf", use_container_width=True, key="pdf_download_button")
                    st.markdown("---")
                    
                    est_n = st.selectbox("Estado", ["Esperando", "Preparacion", "Terminado", "Entregado"], index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(tk['Estado_Fabricacion']))
                    if st.button("ACTUALIZAR ESTADO", use_container_width=True):
                        idx = df[df['Nro_Ppto'].astype(str) == ppto_id].index[0] + 2
                        ws_p.update_cell(idx, 3, est_n)
                        traer_datos("Historial")[1].append_row([ppto_id, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state['user'], f"Estado cambiado a {est_n}"])
                        st.success(f"Estado MAG-{ppto_id} Actualizado"); st.rerun()
                    st.markdown(f"<p style='text-align: center; color: #6B778C; font-size: 0.9em; margin-top: 15px;'>Creado: {tk['Fecha_Carga']}</p>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

    # --- REPORTE SEMANAL ---
    elif nav == "📊 Reportes Semanales":
        st.title("📈 Reportes e Insights (Jira Style)")
        df_h, _ = traer_datos("Historial")
        if not df_h.empty:
            st.markdown("### Actividad por Operador")
            df_h['f'] = pd.to_datetime(df_h['Fecha_Hora'], dayfirst=True, errors='coerce')
            df_h = df_h.dropna(subset=['f'])
            st.plotly_chart(px.bar(df_h['Usuario'].value_counts().reset_index(), x='Usuario', y='count', color='Usuario', labels={'count': 'Total Acciones'}), use_container_width=True)

    # --- NUEVA OBRA ---
    elif nav == "➕ Crear Nuevo Ticket":
        st.title("🆕 Crear Nuevo Ticket de Trabajo")
        with st.form("nuevo_ticket"):
            c1, c2 = st.columns(2)
            n = c1.text_input("🎫 Número de Presupuesto")
            c = c2.text_input("👤 Cliente")
            u = c1.text_input("📍 Localidad / Ubicación")
            m = c1.number_input("💰 Monto Total", min_value=0)
            p = c2.number_input("💸 Seña Inicial", min_value=0)
            i = c2.selectbox("📄 IVA", ["sin iva", "iva 21%"])
            st.markdown("---")
            if st.form_submit_button("CREAR TICKET DE TRABAJO", use_container_width=True):
                if n and c:
                    traer_datos("Proyectos")[1].append_row([n, c, "Esperando", date.today().strftime("%d/%m/%Y"), date.today().strftime("%d/%m/%Y"), m, p, i, "", "", u])
                    st.success(f"Ticket MAG-{n} creado correctamente")
                else:
                    st.error("Nro y Cliente son obligatorios")