import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF
import urllib.parse

# --- CONFIGURACIÓN ---
LOGO_URL = "https://r.jina.ai/i/0586f37648354c4193568c07d3967484"
st.set_page_config(page_title="Magallan Ultra v6", layout="wide")

# --- ESTILOS DE ALTO CONTRASTE ---
st.markdown(f"""
    <style>
    .stApp {{ background: #1a1a2e; color: #ffffff; }}
    input, div[data-baseweb="select"], .stTextArea textarea, div[data-baseweb="input"] {{
        background-color: #ffffff !important; color: #000000 !important;
    }}
    .ticket-card {{
        background: rgba(255, 255, 255, 0.1); border: 1px solid #444;
        border-radius: 10px; padding: 15px; margin-bottom: 10px;
    }}
    .monto-brillante {{ color: #00d2ff; font-size: 1.2em; font-weight: bold; }}
    .alerta-72hs {{ border-left: 6px solid #ff4b4b; background: rgba(255, 75, 75, 0.1); }}
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES ---
def safe_int(v):
    try: return int(float(str(v).replace("$","").replace(".","").strip()))
    except: return 0

def generar_pdf_v6(tk):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=f"ORDEN DE TRABAJO: MAG-{tk['Nro_Ppto']}", ln=True, align='C')
    pdf.set_font("Arial", size=11)
    pdf.ln(10)
    pdf.cell(0, 10, txt=f"Cliente: {tk['Cliente']} | Ubicacion: {tk.get('Ubicacion','S/D')}", ln=True)
    pdf.cell(0, 10, txt=f"Monto: ${tk['Monto_Total_Ars']}", ln=True)
    return pdf.output(dest='S').encode('latin-1', errors='replace')

@st.cache_resource
def g_conn():
    return gspread.authorize(Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    ))

def fetch(sheet_name):
    try:
        sh = g_conn().open("Gestion_Magallan")
        ws = sh.worksheet(sheet_name)
        return pd.DataFrame(ws.get_all_records()), ws
    except: return pd.DataFrame(), None

# --- APP ---
if "authenticated" not in st.session_state:
    st.title("Acceso Grupo Magallan")
    u = st.selectbox("Usuario", ["Jonathan", "Martin", "Jacqueline"])
    p = st.text_input("Contraseña", type="password")
    if st.button("INGRESAR"):
        if str(st.secrets["usuarios"][u]) == p:
            st.session_state.update({"authenticated": True, "user": u})
            st.rerun()
else:
    st.sidebar.image(LOGO_URL)
    menu = st.sidebar.radio("MENÚ", ["📋 PLANTA", "📅 SEGUIMIENTO", "🆕 CARGA RÁPIDA"])

    # 1. PLANTA
    if menu == "📋 PLANTA":
        df, ws = fetch("Proyectos")
        st.title("📋 Control de Planta")
        for i, r in df.iterrows():
            with st.container():
                st.markdown(f"""<div class="ticket-card">
                    <b>MAG-{r['Nro_Ppto']}</b> | {r['Cliente']} <br>
                    <span class="monto-brillante">${r['Monto_Total_Ars']}</span> | 📍 {r.get('Ubicacion','-')}
                </div>""", unsafe_allow_html=True)
                if st.button(f"Gestionar MAG-{r['Nro_Ppto']}", key=f"p_{r['Nro_Ppto']}_{i}"):
                    st.session_state.edit_id = str(r['Nro_Ppto'])

    # 2. SEGUIMIENTO CON AUTO-APROBACIÓN
    elif menu == "📅 SEGUIMIENTO":
        st.title("📅 Seguimiento de Presupuestos")
        df_s, ws_s = fetch("Seguimiento")
        
        with st.expander("➕ Cargar para Seguimiento"):
            with st.form("f_seg"):
                c1, c2 = st.columns(2)
                nom = c1.text_input("Nombre")
                nro = c2.text_input("MAG#")
                tel = c1.text_input("Teléfono (549...)")
                ubi = c2.text_input("Ubicación")
                mon = st.number_input("Monto", min_value=0)
                if st.form_submit_button("AGENDAR"):
                    ws_s.append_row([nom, nro, tel, ubi, mon, datetime.now().strftime("%d/%m/%Y")])
                    st.rerun()

        if not df_s.empty:
            for i, r in df_s.iterrows():
                # Lógica 72hs
                f_env = datetime.strptime(str(r['Fecha_Carga']), "%d/%m/%Y")
                dias = (datetime.now() - f_env).days
                css = "alerta-72hs" if dias >= 3 else ""
                
                st.markdown(f"""<div class="ticket-card {css}">
                    <b>{r['Nombre']} (MAG-{r['Nro_Ppto']})</b> | ${r['Monto']}<br>
                    📍 {r['Ubicacion']} | Tel: {r['Telefono']}
                </div>""", unsafe_allow_html=True)
                
                col_a, col_b = st.columns(2)
                with col_a:
                    wa_msg = urllib.parse.quote(f"Hola {r['Nombre']}, te escribo de Magallan...")
                    st.markdown(f'<a href="https://wa.me/{r["Telefono"]}?text={wa_msg}" target="_blank"><button style="width:100%; background:#25D366; color:white; border:none; padding:8px; border-radius:5px;">WhatsApp</button></a>', unsafe_allow_html=True)
                
                with col_b:
                    # FUNCIÓN DE AUTO-APROBACIÓN
                    if st.button(f"✅ APROBAR", key=f"aprob_{i}"):
                        # 1. Mover a Planta
                        _, ws_p = fetch("Proyectos")
                        ws_p.append_row([r['Nro_Ppto'], r['Nombre'], "Esperando", datetime.now().strftime("%d/%m/%Y"), "", r['Monto'], 0, "sin iva", "", "", r['Ubicacion']])
                        # 2. Eliminar de Seguimiento (borra la fila i+2 considerando encabezado)
                        ws_s.delete_rows(i + 2)
                        st.success(f"MAG-{r['Nro_Ppto']} movido a Planta"); st.rerun()

    # 3. CARGA RÁPIDA (PLANTA)
    elif menu == "🆕 CARGA RÁPIDA":
        with st.form("new_p"):
            st.subheader("Nueva Orden de Planta")
            c1, c2 = st.columns(2)
            n = c1.text_input("MAG#")
            cl = c2.text_input("Cliente")
            mo = st.number_input("Monto")
            if st.form_submit_button("CARGAR"):
                fetch("Proyectos")[1].append_row([n, cl, "Esperando", datetime.now().strftime("%d/%m/%Y"), "", mo])
                st.success("Cargado")