import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fpdf import FPDF
import plotly.express as px

# --- 1. CONFIGURACIÓN Y ESTILO (INDUSTRIAL LIGHT) ---
st.set_page_config(page_title="Grupo Magallan - Gestión Pro", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F4F7F9; color: #1E293B; }
    [data-testid="stMetricValue"] { color: #0284C7; font-weight: 700; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; color: #64748B; }
    .stTabs [aria-selected="true"] { color: #0284C7 !important; border-bottom-color: #0284C7 !important; }
    .obra-header { 
        background: #1E293B; color: white; padding: 15px; border-radius: 8px; 
        margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    .chat-msg { 
        background: white; padding: 10px; border-radius: 5px; 
        border-left: 4px solid #0284C7; margin-bottom: 8px; font-size: 0.9rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCIONES DE DATOS Y SEGURIDAD ---
def limpiar_monto(valor):
    if pd.isna(valor) or valor == "": return 0
    try:
        if isinstance(valor, str):
            valor = valor.replace("$", "").replace(".", "").replace(",", ".").strip()
        return int(float(valor))
    except: return 0

@st.cache_resource(ttl=600)
def conectar_gs():
    try:
        return gspread.authorize(Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        ))
    except Exception as e:
        st.error(f"Error de conexión crítica: {e}")
        return None

def obtener_datos_seguros(nombre_hoja, cols_necesarias):
    """Evita KeyErrors asegurando que las columnas existan o creando la hoja si no existe."""
    try:
        gc = conectar_gs()
        sh = gc.open("Gestion_Magallan")
        try:
            ws = sh.worksheet(nombre_hoja)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=nombre_hoja, rows="100", cols=str(len(cols_necesarias)))
            ws.append_row(cols_necesarias)
        
        df = pd.DataFrame(ws.get_all_records())
        for col in cols_necesarias:
            if col not in df.columns: df[col] = ""
        return df, ws
    except Exception as e:
        st.error(f"Fallo al leer {nombre_hoja}: {e}")
        return pd.DataFrame(columns=cols_necesarias), None

# --- 3. GENERADOR DE PDF (CORRECCIÓN DE ATTRIBUTEERROR) ---
def generar_pdf_orden(tk):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, f"GRUPO MAGALLAN - ORDEN MAG-{tk.get('Nro_Ppto', 'S/N')}", 0, 1, 'C')
        pdf.ln(10)
        
        pdf.set_font("Arial", size=10)
        data = [
            ("Cliente", str(tk.get('Cliente', ''))),
            ("Vendedor", str(tk.get('Vendedor', ''))),
            ("Ubicacion", str(tk.get('Ubicacion', ''))),
            ("Mts2", f"{tk.get('Mts2', '0')} mts2"),
            ("Saldo", f"${limpiar_monto(tk.get('Monto_Total_Ars',0)) - limpiar_monto(tk.get('Pagado_Ars',0))}")
        ]
        
        for label, val in data:
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(40, 8, label, 1, 0, 'L', True)
            pdf.cell(150, 8, val, 1, 1, 'L')
            
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 10); pdf.cell(0, 8, "DETALLES TECNICOS:", 0, 1)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 7, str(tk.get('Materiales_Pendientes', 'Sin notas adicionales.')))
        
        return pdf.output(dest='S').encode('latin-1', errors='replace')
    except Exception as e:
        st.error(f"Error generando PDF: {e}")
        return None

# --- 4. CONTROL DE ACCESO ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    col_l, col_c, col_r = st.columns([1,2,1])
    with col_c:
        st.image("https://via.placeholder.com/150x50?text=GRUPO+MAGALLAN", width=200) # Reemplazar por URL de logo real
        st.subheader("Acceso Magallan Enterprise")
        user = st.selectbox("Operador", ["---", "Jonathan", "Martin", "Jacqueline"])
        pw = st.text_input("Clave de Acceso", type="password")
        if st.button("INICIAR SESIÓN", use_container_width=True):
            if user != "---" and str(st.secrets["usuarios"].get(user)) == pw:
                st.session_state.auth, st.session_state.user = True, user
                st.rerun()
else:
    # --- 5. CARGA DE DATOS CENTRALIZADA ---
    cols_proy = ['Nro_Ppto', 'Cliente', 'Estado_Fabricacion', 'Fecha_Ingreso', 'Vendedor', 'Monto_Total_Ars', 'Pagado_Ars', 'Iva', 'Mts2', 'Materiales_Pendientes', 'Ubicacion']
    cols_hist = ['Nro_Ppto', 'Fecha_Hora', 'Usuario', 'Accion']
    
    df_p, ws_p = obtener_datos_seguros("Proyectos", cols_proy)
    df_h, ws_h = obtener_datos_seguros("Historial", cols_hist)
    
    # Sidebar
    st.sidebar.title(f"👤 {st.session_state.user}")
    menu = st.sidebar.radio("SISTEMA", ["📊 Dashboard", "🏗️ Tablero Planta", "📅 Seguimiento", "➕ Nueva Carga"])

    # --- LÓGICA DE PÁGINAS ---
    if menu == "📊 Dashboard":
        st.subheader("Resumen Ejecutivo")
        total_cobrar = (df_p['Monto_Total_Ars'].apply(limpiar_monto) - df_p['Pagado_Ars'].apply(limpiar_monto)).sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("SALDO PENDIENTE", f"${total_cobrar:,}")
        c2.metric("EN PRODUCCIÓN", len(df_p[df_p['Estado_Fabricacion'] != 'Entregado']))
        c3.metric("COBRADO", f"${df_p['Pagado_Ars'].apply(limpiar_monto).sum():,}")
        
        st.plotly_chart(px.bar(df_p, x='Vendedor', y='Monto_Total_Ars', color='Estado_Fabricacion', title="Ventas por Vendedor"), use_container_width=True)

    elif menu == "🏗️ Tablero Planta":
        st.subheader("Control de Planta y Alertas")
        busqueda = st.text_input("🔍 Buscar Cliente o Nro MAG...")
        
        df_f = df_p[df_p.apply(lambda r: busqueda.lower() in str(r.values).lower(), axis=1)] if busqueda else df_p

        for i, r in df_f.iterrows():
            with st.expander(f"MAG-{r['Nro_Ppto']} | {r['Cliente']} | Saldo: ${limpiar_monto(r['Monto_Total_Ars'])-limpiar_monto(r['Pagado_Ars']):,}"):
                
                tabs = st.tabs(["💎 Valores", "🛠️ Logística/Planta", "💬 Chat Interno", "📜 Historial"])
                
                with tabs[0]: # VALORES
                    c1, c2 = st.columns(2)
                    new_monto = c1.number_input("Monto Total (ARS)", value=limpiar_monto(r['Monto_Total_Ars']), key=f"mt_{i}")
                    new_pagado = c2.number_input("Monto Pagado (ARS)", value=limpiar_monto(r['Pagado_Ars']), key=f"mp_{i}")
                    new_ubi = st.text_input("Ubicación", value=str(r['Ubicacion']), key=f"ub_{i}")
                    if st.button("Guardar Valores", key=f"sv_{i}"):
                        ws_p.update_cell(i+2, 6, new_monto); ws_p.update_cell(i+2, 7, new_pagado); ws_p.update_cell(i+2, 11, new_ubi)
                        ws_h.append_row([r['Nro_Ppto'], datetime.now().strftime("%d/%m %H:%M"), st.session_state.user, f"Actualizó montos a ${new_monto}"])
                        st.success("Actualizado"); st.rerun()

                with tabs[1]: # LOGÍSTICA
                    new_mat = st.text_area("Materiales/Notas", value=str(r['Materiales_Pendientes']), key=f"mat_{i}")
                    new_est = st.selectbox("Estado", ["Esperando", "Preparacion", "Terminado", "Entregado"], index=0, key=f"est_{i}")
                    if st.button("Actualizar Planta", key=f"pl_{i}"):
                        ws_p.update_cell(i+2, 10, new_mat); ws_p.update_cell(i+2, 3, new_est)
                        ws_h.append_row([r['Nro_Ppto'], datetime.now().strftime("%d/%m %H:%M"), st.session_state.user, f"Cambio estado a {new_est}"])
                        st.success("Planta al día"); st.rerun()
                    
                    pdf = generar_pdf_orden(r)
                    if pdf: st.download_button("📥 DESCARGAR PDF OFICIAL", pdf, f"MAG_{r['Nro_Ppto']}.pdf", key=f"pdf_{i}")

                with tabs[2]: # CHAT (Usando la misma lógica de historial pero filtrada)
                    msg = st.text_input("Escribe un mensaje para el equipo...", key=f"chat_in_{i}")
                    if st.button("Enviar Mensaje", key=f"chat_bt_{i}"):
                        ws_h.append_row([r['Nro_Ppto'], datetime.now().strftime("%d/%m %H:%M"), st.session_state.user, f"CHAT: {msg}"])
                        st.rerun()
                    
                    msgs_obra = df_h[df_h['Nro_Ppto'] == r['Nro_Ppto']]
                    for _, m in msgs_obra.iloc[::-1].iterrows():
                        st.markdown(f'<div class="chat-msg"><b>{m["Usuario"]}</b> ({m["Fecha_Hora"]}): {m["Accion"]}</div>', unsafe_allow_html=True)

                with tabs[3]: # HISTORIAL COMPLETO
                    st.dataframe(df_h[df_h['Nro_Ppto'] == r['Nro_Ppto']], use_container_width=True)

    elif menu == "➕ Nueva Carga":
        with st.form("nueva_obra"):
            st.subheader("Carga de Nuevo Proyecto")
            c1, c2, c3 = st.columns(3)
            n_mag = c1.text_input("MAG#")
            n_cli = c2.text_input("Cliente")
            n_ven = c3.selectbox("Vendedor", ["Jonathan", "Martin", "Jacqueline"])
            n_ubi = st.text_input("Localidad / Ubicación")
            n_mts = st.number_input("Superficie (mts2)", value=0.0)
            n_tot = st.number_input("Presupuesto Total ($)", value=0)
            if st.form_submit_button("INGRESAR A SISTEMA"):
                ws_p.append_row([n_mag, n_cli, "Esperando", datetime.now().strftime("%d/%m/%Y"), n_ven, n_tot, 0, "No", n_mts, "", n_ubi])
                ws_h.append_row([n_mag, datetime.now().strftime("%d/%m %H:%M"), st.session_state.user, "Creó el proyecto"])
                st.success("Proyecto registrado con éxito"); st.balloons()

    if st.sidebar.button("SALIR"):
        st.session_state.auth = False
        st.rerun()