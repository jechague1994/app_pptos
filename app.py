import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
from fpdf import FPDF
import plotly.express as px

# URL del logo oficial de Grupo Magallan
LOGO_URL = "https://r.jina.ai/i/0586f37648354c4193568c07d3967484"

# 1. DISEÑO DE INTERFAZ ACTUALIZADO
st.set_page_config(page_title="Magallan | Gestión Integral", layout="wide")

st.markdown(f"""
    <style>
    .stApp {{ background-color: #F4F5F7; }}
    .ticket-card {{ 
        background-color: white; padding: 18px; border-radius: 8px; 
        border-left: 10px solid #DFE1E6; margin-bottom: 12px; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); font-family: sans-serif;
    }}
    .status-terminado {{ border-left-color: #36B37E !important; }}
    .status-atrasado {{ border-left-color: #FF5630 !important; }}
    .status-proceso {{ border-left-color: #0052CC !important; }}
    .status-pagado {{ border-left-color: #6554C0 !important; background-color: #EAE6FF !important; }}
    .sidebar-mag {{ background-color: #FAFBFC; padding: 20px; border-radius: 10px; border: 1px solid #DFE1E6; }}
    .saldo-badge {{ background-color: #FFFAE6; color: #826a00; padding: 5px 10px; border-radius: 15px; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)

# 2. GENERADOR DE PDF CON LOGO Y UBICACIÓN
def generar_pdf_orden(tk):
    pdf = FPDF()
    pdf.add_page()
    try: pdf.image(LOGO_URL, x=10, y=8, w=50)
    except: pdf.text(10, 15, "GRUPO MAGALLAN")
    pdf.ln(25)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=f"ORDEN DE TRABAJO: MAG-{tk['Nro_Ppto']}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12)
    pdf.cell(100, 8, txt=f"Cliente: {tk['Cliente']}")
    pdf.cell(100, 8, txt=f"Ubicación: {tk.get('Ubicacion', 'No informada')}", ln=True)
    pdf.cell(100, 8, txt=f"Fecha Entrega: {tk['Fecha_Entrega']}", ln=True)
    
    # Cálculos Financieros
    total = int(tk['Monto_Total_Ars'])
    pagado = int(tk.get('Pagado_Ars', 0)) if str(tk.get('Pagado_Ars')).isdigit() else 0
    saldo = total - pagado
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 8, txt=f"TOTAL: ${total}")
    pdf.cell(100, 8, txt=f"SALDO A COBRAR: ${saldo}", ln=True)
    
    pdf.ln(10)
    pdf.cell(0, 10, txt="Detalle de Materiales / Notas:", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, txt=str(tk['Materiales_Pendientes']))
    return pdf.output(dest='S').encode('latin-1')

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
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.image(LOGO_URL)
        u = st.selectbox("Usuario", ["---"] + list(st.secrets["usuarios"].keys()))
        p = st.text_input("Contraseña", type="password")
        if st.button("ACCEDER AL SISTEMA", use_container_width=True):
            if u != "---" and str(st.secrets["usuarios"][u]).strip() == p.strip():
                st.session_state.update({"authenticated": True, "user": u})
                st.rerun()
else:
    # MENÚ LATERAL
    st.sidebar.image(LOGO_URL, use_container_width=True)
    st.sidebar.write(f"👷 *Operador:* {st.session_state['user']}")
    nav = st.sidebar.radio("NAVEGACIÓN", ["📋 Panel de Control", "📈 Reportes", "➕ Nueva Carga"])
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["authenticated"]; st.rerun()

    # --- PANEL DE CONTROL ---
    if nav == "📋 Panel de Control":
        df, ws = traer_datos("Proyectos")
        st.title("📋 Estado de Planta y Logística")
        filtro = st.text_input("🔍 Buscar por Cliente o Localidad...")
        
        if not df.empty:
            for _, r in df.iterrows():
                # Búsqueda en nombre o ubicación
                if filtro.lower() in str(r['Cliente']).lower() or filtro.lower() in str(r.get('Ubicacion','')).lower():
                    # Lógica de Saldos y Colores
                    total = int(r['Monto_Total_Ars'])
                    pago = int(r.get('Pagado_Ars', 0)) if str(r.get('Pagado_Ars')).isdigit() else 0
                    saldo = total - pago
                    
                    try: vence = pd.to_datetime(r['Fecha_Entrega'], dayfirst=True).date() < date.today()
                    except: vence = False
                    
                    # Determinar color
                    if saldo <= 0: clase = "status-pagado"
                    elif str(r['Estado_Fabricacion']).lower() in ["terminado", "entregado"]: clase = "status-terminado"
                    elif vence: clase = "status-atrasado"
                    else: clase = "status-proceso"
                    
                    st.markdown(f"""
                        <div class='ticket-card {clase}'>
                            <b>MAG-{r['Nro_Ppto']}</b> | {r['Cliente']} | 📍 {r.get('Ubicacion', 'S/D')} | 
                            <b>Saldo: ${saldo}</b>
                        </div>
                        """, unsafe_allow_html=True)
            
            st.markdown("---")
            seleccion = st.selectbox("Seleccione Obra para Detalle/PDF:", ["---"] + [f"{r['Nro_Ppto']} - {r['Cliente']}" for _, r in df.iterrows()])
            
            if seleccion != "---":
                ppto_id = str(seleccion.split(" - ")[0])
                tk = df[df['Nro_Ppto'].astype(str) == ppto_id].iloc[0]
                
                c_form, c_pdf = st.columns([2, 1])
                with c_form:
                    with st.form("edicion_final"):
                        f_u = st.text_input("Localidad / Ubicación", value=tk.get('Ubicacion', ''))
                        f_m = st.number_input("Monto Total ($)", value=int(tk['Monto_Total_Ars']))
                        f_p = st.number_input("Pagado ($)", value=int(tk.get('Pagado_Ars', 0) if str(tk.get('Pagado_Ars')).isdigit() else 0))
                        f_i = st.selectbox("IVA", ["sin iva", "iva 21%"], index=0 if "sin" in str(tk['IVA']).lower() else 1)
                        f_n = st.text_area("Notas Técnicas", value=tk['Materiales_Pendientes'])
                        
                        if st.form_submit_button("GUARDAR CAMBIOS"):
                            idx = df[df['Nro_Ppto'].astype(str) == ppto_id].index[0] + 2
                            ws.update_cell(idx, 6, f_m); ws.update_cell(idx, 7, f_p)
                            ws.update_cell(idx, 8, f_i); ws.update_cell(idx, 10, f_n); ws.update_cell(idx, 11, f_u)
                            traer_datos("Historial")[1].append_row([ppto_id, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state['user'], "Actualización General"])
                            st.success("Dato Guardado"); st.rerun()

                with c_pdf:
                    st.markdown("<div class='sidebar-mag'>", unsafe_allow_html=True)
                    s_actual = f_m - f_p
                    if s_actual <= 0: st.success("✅ TOTALMENTE PAGADO")
                    else: st.warning(f"⚠️ PENDIENTE: ${s_actual}")
                    
                    st.download_button("📄 GENERAR ORDEN PDF", data=generar_pdf_orden(tk), file_name=f"MAG_{ppto_id}.pdf", use_container_width=True)
                    st.markdown("---")
                    est_n = st.selectbox("Estado", ["Esperando", "Preparacion", "Terminado", "Entregado"], index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(tk['Estado_Fabricacion']))
                    if st.button("ACTUALIZAR ESTADO", use_container_width=True):
                        idx = df[df['Nro_Ppto'].astype(str) == ppto_id].index[0] + 2
                        ws.update_cell(idx, 3, est_n)
                        traer_datos("Historial")[1].append_row([ppto_id, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state['user'], f"Estado: {est_n}"])
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    # --- REPORTE SEMANAL ---
    elif nav == "📈 Reportes":
        st.title("📈 Rendimiento del Taller")
        df_h, _ = traer_datos("Historial")
        if not df_h.empty:
            df_h['f'] = pd.to_datetime(df_h['Fecha_Hora'], dayfirst=True, errors='coerce')
            df_h = df_h.dropna(subset=['f'])
            st.plotly_chart(px.bar(df_h['Usuario'].value_counts().reset_index(), x='Usuario', y='count', title="Acciones por Usuario"))

    # --- NUEVA OBRA ---
    elif nav == "➕ Nueva Carga":
        with st.form("nuevo"):
            st.subheader("Alta de Presupuesto")
            n = st.text_input("Número Ppto")
            c = st.text_input("Cliente")
            u = st.text_input("Localidad")
            m = st.number_input("Total", min_value=0)
            p = st.number_input("Seña", min_value=0)
            i = st.selectbox("IVA", ["sin iva", "iva 21%"])
            if st.form_submit_button("CREAR"):
                traer_datos("Proyectos")[1].append_row([n, c, "Esperando", date.today().strftime("%d/%m/%Y"), date.today().strftime("%d/%m/%Y"), m, p, i, "", "", u])
                st.success("Creado correctamente")