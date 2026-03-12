import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
from fpdf import FPDF
import plotly.express as px

# URL del logo oficial de Grupo Magallan
LOGO_URL = "https://r.jina.ai/i/0586f37648354c4193568c07d3967484"

# 1. CONFIGURACIÓN DE INTERFAZ Y ESTILOS AVANZADOS
st.set_page_config(page_title="Magallan Enterprise", layout="wide")

st.markdown(f"""
    <style>
    /* Fondo con mosaico sutil y moderno */
    .stApp {{
        background: linear-gradient(rgba(244, 245, 247, 0.95), rgba(244, 245, 247, 0.95)), 
                    url("{LOGO_URL}");
        background-repeat: repeat;
        background-size: 120px;
        background-attachment: fixed;
    }}
    
    /* Contenedores Glassmorphism */
    .main-card {{
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(10px);
        padding: 30px;
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
        margin-bottom: 20px;
    }}

    /* Tarjetas de Obra mejoradas */
    .obra-card {{
        background: white;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 15px;
        border: 1px solid #E1E4E8;
        transition: transform 0.2s ease;
    }}
    .obra-card:hover {{ transform: translateY(-3px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
    
    /* Estados con colores sólidos y brillantes */
    .border-pagado {{ border-left: 10px solid #6554C0 !important; background-color: #F4F2FF !important; }}
    .border-terminado {{ border-left: 10px solid #36B37E !important; }}
    .border-proceso {{ border-left: 10px solid #0052CC !important; }}
    .border-atrasado {{ border-left: 10px solid #FF5630 !important; }}

    /* Botonera */
    .stButton > button {{
        width: 100%;
        border-radius: 8px !important;
        height: 45px;
        font-weight: bold !important;
        text-transform: uppercase;
    }}
    </style>
    """, unsafe_allow_html=True)

# 2. FUNCIONES DE SEGURIDAD PARA DATOS (Evita ValueError/TypeError)
def limpiar_monto(valor):
    """Convierte cualquier entrada a un número entero seguro."""
    try:
        if pd.isna(valor) or valor == "": return 0
        return int(float(str(valor).replace("$", "").replace(".", "").strip()))
    except: return 0

def generar_pdf_pro(tk):
    pdf = FPDF()
    pdf.add_page()
    try: pdf.image(LOGO_URL, x=10, y=8, w=45)
    except: pdf.text(10, 15, "GRUPO MAGALLAN")
    pdf.ln(25)
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=f"ORDEN DE TRABAJO: MAG-{tk['Nro_Ppto']}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12)
    pdf.cell(100, 10, txt=f"Cliente: {str(tk['Cliente'])}")
    pdf.cell(100, 10, txt=f"Ubicacion: {str(tk.get('Ubicacion', 'S/D'))}", ln=True)
    
    total = limpiar_monto(tk['Monto_Total_Ars'])
    pago = limpiar_monto(tk.get('Pagado_Ars', 0))
    saldo = total - pago
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, txt=f"Total: ${total}")
    pdf.cell(100, 10, txt=f"Saldo: ${saldo}", ln=True)
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, txt="Notas y Materiales:", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, txt=str(tk['Materiales_Pendientes']).replace('\n', ' '))
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# 3. CONEXIÓN
@st.cache_resource
def conectar():
    return gspread.authorize(Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    ))

def get_data(sheet):
    try:
        ws = conectar().open("Gestion_Magallan").worksheet(sheet)
        return pd.DataFrame(ws.get_all_records()), ws
    except: return pd.DataFrame(), None

# 4. APLICACIÓN PRINCIPAL
if "authenticated" not in st.session_state:
    st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<div class='main-card' style='text-align: center;'>", unsafe_allow_html=True)
        st.image(LOGO_URL, width=180)
        st.subheader("Acceso Magallan Enterprise")
        u = st.selectbox("Operador", ["---"] + list(st.secrets["usuarios"].keys()))
        p = st.text_input("Clave de Acceso", type="password")
        if st.button("INICIAR SESIÓN"):
            if u != "---" and str(st.secrets["usuarios"][u]).strip() == p.strip():
                st.session_state.update({"authenticated": True, "user": u})
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
else:
    # Sidebar
    st.sidebar.image(LOGO_URL, use_container_width=True)
    st.sidebar.markdown(f"<h3 style='text-align: center;'>{st.session_state['user']}</h3>", unsafe_allow_html=True)
    nav = st.sidebar.radio("SISTEMA", ["📋 BACKLOG", "📊 MÉTRICAS", "🆕 CARGA"])
    if st.sidebar.button("SALIR"):
        del st.session_state["authenticated"]; st.rerun()

    if nav == "📋 BACKLOG":
        df, ws = get_data("Proyectos")
        st.markdown("<div class='main-card'><h1>📋 Control de Planta</h1>", unsafe_allow_html=True)
        busc = st.text_input("🔍 Buscar por Cliente, Nro o Localidad...")
        
        if not df.empty:
            for _, r in df.iterrows():
                if busc.lower() in str(r['Cliente']).lower() or busc.lower() in str(r.get('Ubicacion','')).lower() or busc.lower() in str(r['Nro_Ppto']).lower():
                    # Cálculos Seguros
                    total = limpiar_monto(r['Monto_Total_Ars'])
                    pago = limpiar_monto(r.get('Pagado_Ars', 0))
                    saldo = total - pago
                    
                    clase = "border-pagado" if saldo <= 0 else ("border-terminado" if str(r['Estado_Fabricacion']).lower() == "terminado" else "border-proceso")
                    
                    st.markdown(f"""
                        <div class='obra-card {clase}'>
                            <div style='display: flex; justify-content: space-between;'>
                                <span><b>MAG-{r['Nro_Ppto']}</b> | {r['Cliente']}</span>
                                <span style='color: #6554C0;'><b>SALDO: ${saldo}</b></span>
                            </div>
                            <div style='font-size: 0.85em; color: #6B778C; margin-top: 5px;'>
                                📍 {r.get('Ubicacion', 'Sin Dirección')} | 📅 Entrega: {r['Fecha_Entrega']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
            
            st.markdown("---")
            sel = st.selectbox("Seleccione para Editar o Imprimir:", ["---"] + [f"{r['Nro_Ppto']} - {r['Cliente']}" for _, r in df.iterrows()])
            
            if sel != "---":
                id_sel = str(sel.split(" - ")[0])
                tk = df[df['Nro_Ppto'].astype(str) == id_sel].iloc[0]
                
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    with st.form("edit"):
                        f_u = st.text_input("Ubicación", value=tk.get('Ubicacion', ''))
                        f_m = st.number_input("Monto Total", value=limpiar_monto(tk['Monto_Total_Ars']))
                        f_p = st.number_input("Pagado", value=limpiar_monto(tk.get('Pagado_Ars', 0)))
                        f_n = st.text_area("Notas", value=str(tk['Materiales_Pendientes']))
                        if st.form_submit_button("ACTUALIZAR DATOS"):
                            idx = df[df['Nro_Ppto'].astype(str) == id_sel].index[0] + 2
                            ws.update_cell(idx, 6, f_m); ws.update_cell(idx, 7, f_p); ws.update_cell(idx, 10, f_n); ws.update_cell(idx, 11, f_u)
                            get_data("Historial")[1].append_row([id_sel, datetime.now().strftime("%d/%m/%Y"), st.session_state['user'], "Update"])
                            st.rerun()
                
                with col_b:
                    st.download_button("📄 DESCARGAR ORDEN PDF", data=generar_pdf_pro(tk), file_name=f"MAG_{id_sel}.pdf")
                    st.markdown("---")
                    est = st.selectbox("Estado Actual", ["Esperando", "Preparacion", "Terminado", "Entregado"], index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(tk['Estado_Fabricacion']))
                    if st.button("CAMBIAR ESTADO"):
                        idx = df[df['Nro_Ppto'].astype(str) == id_sel].index[0] + 2
                        ws.update_cell(idx, 3, est)
                        st.rerun()

    elif nav == "📊 MÉTRICAS":
        st.title("Estadísticas de Gestión")
        df_h, _ = get_data("Historial")
        if not df_h.empty:
            st.plotly_chart(px.pie(df_h, names='Usuario', title="Actividad por Operador", hole=0.4))

    elif nav == "🆕 CARGA":
        with st.form("new"):
            st.subheader("Nuevo Presupuesto")
            c1, c2 = st.columns(2)
            n = c1.text_input("Número Ppto")
            cl = c2.text_input("Cliente")
            ub = c1.text_input("Localidad")
            mt = c2.number_input("Monto Total", min_value=0)
            if st.form_submit_button("DAR DE ALTA"):
                get_data("Proyectos")[1].append_row([n, cl, "Esperando", date.today().strftime("%d/%m/%Y"), "", mt, 0, "sin iva", "", "", ub])
                st.success("Cargado!")