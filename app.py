import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF
import plotly.express as px

# --- CONFIGURACIÓN DE MARCA ---
LOGO_URL = "https://r.jina.ai/i/0586f37648354c4193568c07d3967484"

st.set_page_config(page_title="Magallan Ultra v4", layout="wide")

# --- ESTILOS PREMIUM (Glassmorphism & Alerts) ---
st.markdown(f"""
    <style>
    .stApp {{
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        background-attachment: fixed; color: #E0E0E0;
    }}
    .ticket-container {{
        background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px);
        border-radius: 12px; padding: 15px; margin-bottom: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        display: flex; justify-content: space-between; align-items: center;
    }}
    .alert-inactive {{ border-left: 5px solid #FFAB00; background: rgba(255, 171, 0, 0.1); }}
    .alert-followup {{ border-left: 5px solid #00D2FF; background: rgba(0, 210, 255, 0.1); }}
    .status-badge {{ padding: 4px 10px; border-radius: 15px; font-size: 0.75em; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES NÚCLEO ---
def safe_int(val):
    try: return int(float(str(val).replace("$","").replace(".","").strip()))
    except: return 0

def generar_pdf_final(tk):
    pdf = FPDF()
    pdf.add_page()
    try: pdf.image(LOGO_URL, x=10, y=8, w=40)
    except: pdf.text(10, 15, "GRUPO MAGALLAN")
    pdf.ln(20)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=f"ORDEN DE TRABAJO: MAG-{str(tk['Nro_Ppto'])}", ln=True, align='C')
    pdf.set_font("Arial", size=11)
    pdf.ln(10)
    pdf.cell(0, 10, txt=f"Cliente: {str(tk['Cliente'])} | Ubicacion: {str(tk.get('Ubicacion','S/D'))}", ln=True)
    pdf.cell(0, 10, txt=f"Total: ${safe_int(tk['Monto_Total_Ars'])} | Saldo: ${safe_int(tk['Monto_Total_Ars']) - safe_int(tk.get('Pagado_Ars', 0))}", ln=True)
    pdf.ln(5); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 10, "Notas Técnicas:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 7, txt=str(tk['Materiales_Pendientes']).replace('\n', ' '))
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
    st.image(LOGO_URL, width=200)
    u = st.selectbox("Usuario", ["---", "Jonathan", "Martin", "Jacqueline"])
    p = st.text_input("Clave", type="password")
    if st.button("ENTRAR"):
        if u != "---" and str(st.secrets["usuarios"][u]) == p:
            st.session_state.update({"authenticated": True, "user": u})
            st.rerun()
else:
    st.sidebar.image(LOGO_URL)
    menu = st.sidebar.radio("SISTEMA", ["📋 TABLERO PLANTA", "📅 AGENDA SEGUIMIENTO", "📊 MÉTRICAS", "🆕 CARGA"])

    # 1. TABLERO DE PLANTA CON ALERTAS DE INACTIVIDAD
    if menu == "📋 TABLERO PLANTA":
        df, ws = fetch("Proyectos")
        df_h, _ = fetch("Historial")
        st.title("📋 Control de Planta & Alertas")
        
        busq = st.text_input("🔍 Buscar Cliente o MAG#")
        
        for idx, r in df.iterrows():
            if busq.lower() in str(r['Cliente']).lower() or busq.lower() in str(r['Nro_Ppto']).lower():
                # Lógica de Inactividad (48hs)
                last_act = df_h[df_h['Nro_Ppto'].astype(str) == str(r['Nro_Ppto'])]
                is_inactive = False
                if not last_act.empty:
                    last_date = pd.to_datetime(last_act.iloc[-1]['Fecha_Hora'], dayfirst=True)
                    if datetime.now() - last_date > timedelta(hours=48):
                        is_inactive = True
                
                saldo = safe_int(r['Monto_Total_Ars']) - safe_int(r.get('Pagado_Ars', 0))
                clase_alerta = "alert-inactive" if is_inactive else ""
                
                st.markdown(f"""
                <div class="ticket-container {clase_alerta}">
                    <div>
                        <b>MAG-{r['Nro_Ppto']}</b> | {r['Cliente']} {'⚠️ (Inactivo)' if is_inactive else ''}<br>
                        <span style="font-size:0.8em; color:#aaa;">📍 {r.get('Ubicacion','S/D')}</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="color:#00D2FF; font-weight:bold;">${saldo}</span><br>
                        <button style="border:none; background:none; cursor:pointer;" onclick="window.location.reload()">✏️ Editar</button>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"✏️ Gestionar MAG-{r['Nro_Ppto']}", key=f"btn_{r['Nro_Ppto']}"):
                    st.session_state.edit_id = str(r['Nro_Ppto'])

        if "edit_id" in st.session_state:
            st.divider()
            tk = df[df['Nro_Ppto'].astype(str) == st.session_state.edit_id].iloc[0]
            t1, t2, t3, t4 = st.tabs(["💰 VALORES", "🏗️ PLANTA", "💬 CHAT", "📜 HISTORIAL"])
            
            with t1:
                with st.form("f1"):
                    v1 = st.number_input("Monto", value=safe_int(tk['Monto_Total_Ars']))
                    v2 = st.number_input("Pagado", value=safe_int(tk.get('Pagado_Ars', 0)))
                    if st.form_submit_button("GUARDAR"):
                        row = df[df['Nro_Ppto'].astype(str) == st.session_state.edit_id].index[0] + 2
                        ws.update_cell(row, 6, v1); ws.update_cell(row, 7, v2)
                        fetch("Historial")[1].append_row([st.session_state.edit_id, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state.user, "Update Valores"])
                        st.rerun()
            
            with t2:
                with st.form("f2"):
                    m_p = st.text_area("Notas Planta", value=str(tk['Materiales_Pendientes']))
                    est = st.selectbox("Estado", ["Esperando", "Preparacion", "Terminado", "Entregado"], index=0)
                    if st.form_submit_button("ACTUALIZAR"):
                        row = df[df['Nro_Ppto'].astype(str) == st.session_state.edit_id].index[0] + 2
                        ws.update_cell(row, 3, est); ws.update_cell(row, 10, m_p)
                        st.rerun()
            
            with t3:
                df_c, ws_c = fetch("Chat_Interno")
                msgs = df_c[df_c['Nro_Ppto'].astype(str) == st.session_state.edit_id]
                for _, m in msgs.iterrows(): st.write(f"*{m['Usuario']}*: {m['Mensaje']}")
                msg_n = st.text_input("Nuevo mensaje...")
                if st.button("Enviar"):
                    ws_c.append_row([st.session_state.edit_id, st.session_state.user, datetime.now().strftime("%d/%m/%Y %H:%M"), msg_n])
                    st.rerun()

            st.download_button("📄 DESCARGAR PDF", data=generar_pdf_final(tk), file_name=f"MAG_{st.session_state.edit_id}.pdf")
            if st.button("Cerrar"): del st.session_state.edit_id; st.rerun()

    # 2. AGENDA DE SEGUIMIENTO (72hs)
    elif menu == "📅 AGENDA SEGUIMIENTO":
        st.title("📅 Agenda de Seguimiento (No Aprobados)")
        df_p, ws_p = fetch("Presupuestos_No_Aprobados")
        
        if not df_p.empty:
            df_p['Fecha_Envio'] = pd.to_datetime(df_p['Fecha_Envio'], dayfirst=True)
            for idx, r in df_p.iterrows():
                dias_pasados = (datetime.now() - r['Fecha_Envio']).days
                alerta_agenda = "alert-followup" if dias_pasados >= 3 else ""
                
                st.markdown(f"""
                <div class="ticket-container {alerta_agenda}">
                    <div>
                        <b>{r['Cliente']}</b> | Enviado: {r['Fecha_Envio'].strftime('%d/%m/%Y')}<br>
                        <span style="font-size:0.8em; color:#00D2FF;">{'🔔 RECUERDO: Toca enviar mensaje (72hs cumplidas)' if dias_pasados >= 3 else f'Faltan {3-dias_pasados} días para el recordatorio'}</span>
                    </div>
                    <button style="background:#36B37E; color:white; border:none; padding:5px 10px; border-radius:5px;">Aprobar ✅</button>
                </div>
                """, unsafe_allow_html=True)
        
        with st.expander("➕ Agregar Presupuesto para Seguimiento"):
            with st.form("f_agenda"):
                c_n = st.text_input("Nombre Cliente")
                m_n = st.number_input("Monto Cotizado")
                if st.form_submit_button("AGENDAR"):
                    ws_p.append_row([c_n, m_n, datetime.now().strftime("%d/%m/%Y"), "Pendiente"])
                    st.success("Agendado"); st.rerun()

    elif menu == "📊 MÉTRICAS":
        df_h, _ = fetch("Historial")
        st.plotly_chart(px.bar(df_h['Usuario'].value_counts().reset_index(), x='index', y='Usuario', title="Acciones por Operador"))

    elif menu == "🆕 CARGA":
        with st.form("new"):
            n = st.text_input("MAG#")
            c = st.text_input("Cliente")
            u = st.text_input("Localidad")
            m = st.number_input("Total")
            if st.form_submit_button("CREAR"):
                fetch("Proyectos")[1].append_row([n, c, "Esperando", datetime.now().strftime("%d/%m/%Y"), "", m, 0, "sin iva", "", "", u])
                st.success("Creado")