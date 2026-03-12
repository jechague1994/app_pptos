import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fpdf import FPDF
import urllib.parse
import plotly.express as px
import io

# --- 1. CONFIGURACIÓN Y ESTILO INDUSTRIAL ---
LOGO_URL = "https://r.jina.ai/i/0586f37648354c4193568c07d3967484"
st.set_page_config(page_title="Magallan Ultra - Sistema Integral", layout="wide")

st.markdown(f"""
    <style>
    .stApp {{ background-color: #0E1117; color: #E4E6EB; }}
    
    /* Contenedores de Métricas (Dashboard) */
    .metric-container {{
        background: linear-gradient(135deg, #1c1f26 0%, #111418 100%);
        border: 1px solid #30363d;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    
    /* Tarjetas de Proyectos */
    .ticket-card {{ 
        background: #1C1F26; border: 1px solid #30363D; border-left: 6px solid #0052CC;
        border-radius: 12px; padding: 18px; margin-bottom: 12px; transition: 0.3s;
    }}
    .ticket-card:hover {{ transform: translateY(-3px); border-color: #58a6ff; }}
    .ticket-card-alerta {{ border-left-color: #FF5630; background: #241B1B; }}
    .ticket-card-ok {{ border-left-color: #36B37E; background: #1B241E; }}
    
    /* UI Components */
    .stButton>button {{ border-radius: 8px; font-weight: 600; border: none; transition: 0.2s; }}
    .monto-highlight {{ color: #00D2FF; font-size: 1.5em; font-weight: bold; }}
    .tag-vendedor {{ background: #30363D; color: #8B949E; padding: 4px 12px; border-radius: 20px; font-size: 0.8em; }}
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCIONES NÚCLEO Y ROBUSTEZ ---
def safe_int(valor):
    try:
        if isinstance(valor, str):
            valor = valor.replace("$", "").replace(".", "").replace(",", ".").strip()
        return int(float(valor))
    except: return 0

@st.cache_resource(ttl=300)
def conectar_gs():
    try:
        return gspread.authorize(Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        ))
    except Exception as e:
        st.error(f"Error de conexión con Google: {e}")
        return None

def fetch_data(sheet_name):
    try:
        gc = conectar_gs()
        if gc:
            sh = gc.open("Gestion_Magallan")
            ws = sh.worksheet(sheet_name)
            df = pd.DataFrame(ws.get_all_records())
            return df.fillna(""), ws
    except: pass
    return pd.DataFrame(), None

def registrar_log(nro, user, accion):
    _, ws_h = fetch_data("Historial")
    if ws_h:
        try: ws_h.append_row([str(nro), datetime.now().strftime("%d/%m/%Y %H:%M"), user, accion])
        except: pass

def generar_pdf_orden(tk):
    pdf = FPDF()
    pdf.add_page()
    try: pdf.image(LOGO_URL, x=10, y=8, w=40)
    except: pass
    pdf.set_font("Arial", 'B', 16)
    pdf.ln(20)
    pdf.cell(190, 10, f"ORDEN DE PRODUCCIÓN: MAG-{tk.get('Nro_Ppto','')}", 0, 1, 'C')
    pdf.set_font("Arial", size=10)
    pdf.ln(10)
    
    datos = [
        ("Cliente", tk.get('Cliente','S/D')), ("Vendedor", tk.get('Vendedor','S/D')),
        ("Ubicación", tk.get('Ubicacion','S/D')), ("Superficie", f"{tk.get('Mts2',0)} mts2"),
        ("Fecha", tk.get('Fecha_Ingreso','S/D')), ("Monto Total", f"${safe_int(tk.get('Monto_Total_Ars',0))}")
    ]
    for label, val in datos:
        pdf.set_font("Arial", 'B', 10); pdf.cell(40, 8, f"{label}:", 0)
        pdf.set_font("Arial", size=10); pdf.cell(150, 8, str(val), 0, 1)
    
    pdf.ln(5); pdf.set_font("Arial", 'B', 11); pdf.cell(190, 8, "DETALLES DE MATERIALES Y FABRICACIÓN:", "B", 1)
    pdf.set_font("Arial", size=10); pdf.ln(2)
    pdf.multi_cell(0, 7, str(tk.get('Materiales_Pendientes', 'Sin especificaciones técnicas.')))
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 3. SISTEMA DE ACCESO ---
if "authenticated" not in st.session_state:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.image(LOGO_URL, width=220)
        st.subheader("Control de Gestión")
        u = st.selectbox("Usuario", ["---", "Jonathan", "Martin", "Jacqueline"])
        p = st.text_input("Contraseña", type="password")
        if st.button("ACCEDER", use_container_width=True):
            if u != "---" and str(st.secrets["usuarios"][u]) == p.strip():
                st.session_state.update({"authenticated": True, "user": u})
                st.rerun()
else:
    # --- 4. DASHBOARD SUPERIOR (RESUMEN FINANCIERO) ---
    df_p, ws_p = fetch_data("Proyectos")
    df_s, ws_s = fetch_data("Seguimiento")
    
    st.sidebar.image(LOGO_URL, use_container_width=True)
    st.sidebar.markdown(f"### Operador: *{st.session_state['user']}*")
    menu = st.sidebar.radio("MENÚ", ["📋 TABLERO PLANTA", "📅 SEGUIMIENTO", "📊 MÉTRICAS", "🆕 NUEVA CARGA"])
    
    if not df_p.empty:
        total_p = sum(safe_int(x) for x in df_p['Monto_Total_Ars'])
        pagado_p = sum(safe_int(x) for x in df_p['Pagado_Ars'])
        saldo_total = total_p - pagado_p
        
        st.markdown("### 🏦 Resumen Ejecutivo")
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.markdown(f'<div class="metric-container"><small>SALDO PENDIENTE</small><br><span class="monto-highlight">${saldo_total:,}</span></div>', unsafe_allow_html=True)
        with m2: st.markdown(f'<div class="metric-container"><small>EN PRODUCCIÓN</small><br><span class="monto-highlight">{len(df_p[df_p["Estado_Fabricacion"] != "Entregado"])}</span></div>', unsafe_allow_html=True)
        with m3: st.markdown(f'<div class="metric-container"><small>SEGUIMIENTOS</small><br><span class="monto-highlight">{len(df_s)}</span></div>', unsafe_allow_html=True)
        with m4: st.markdown(f'<div class="metric-container"><small>COBRADO</small><br><span style="color:#36B37E; font-size:1.5em; font-weight:bold;">${pagado_p:,}</span></div>', unsafe_allow_html=True)
        st.markdown("---")

    # --- 5. LÓGICA DE MÓDULOS ---
    if menu == "📋 TABLERO PLANTA":
        c_f1, c_f2 = st.columns([2, 1])
        busq = c_f1.text_input("🔍 Buscar MAG, Cliente o Vendedor...")
        vend_f = c_f2.selectbox("Filtrar por Vendedor", ["Todos", "Jonathan", "Martin", "Jacqueline"])

        if not df_p.empty:
            if vend_f != "Todos": df_p = df_p[df_p['Vendedor'] == vend_f]
            if busq: df_p = df_p[df_p.apply(lambda row: busq.lower() in str(row.values).lower(), axis=1)]

            # Panel de Edición Detallado
            if "edit_id" in st.session_state:
                res = df_p[df_p['Nro_Ppto'].astype(str) == st.session_state.edit_id]
                if not res.empty:
                    tk = res.iloc[0]
                    with st.container(border=True):
                        st.subheader(f"⚙️ Gestión MAG-{st.session_state.edit_id} | {tk['Cliente']}")
                        tab1, tab2, tab3, tab4 = st.tabs(["💵 Caja", "🏗️ Producción", "💬 Chat Interno", "📄 Documentación"])
                        
                        idx_row = df_p[df_p['Nro_Ppto'].astype(str) == st.session_state.edit_id].index[0] + 2
                        
                        with tab1:
                            c1, c2 = st.columns(2)
                            n_tot = c1.number_input("Total ARS", value=safe_int(tk['Monto_Total_Ars']))
                            n_pag = c2.number_input("Pagado ARS", value=safe_int(tk['Pagado_Ars']))
                            if st.button("Guardar Cambios de Caja"):
                                ws_p.update_cell(idx_row, 6, n_tot); ws_p.update_cell(idx_row, 7, n_pag)
                                registrar_log(tk['Nro_Ppto'], st.session_state['user'], f"Update Caja: ${n_pag}/${n_tot}")
                                st.rerun()
                        
                        with tab2:
                            n_est = st.selectbox("Estado Actual", ["Esperando", "Preparacion", "Terminado", "Entregado"], index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(tk['Estado_Fabricacion']) if tk['Estado_Fabricacion'] in ["Esperando", "Preparacion", "Terminado", "Entregado"] else 0)
                            n_mat = st.text_area("Notas Técnicas / Materiales", value=tk['Materiales_Pendientes'])
                            if st.button("Actualizar Planta"):
                                ws_p.update_cell(idx_row, 3, n_est); ws_p.update_cell(idx_row, 10, n_mat)
                                registrar_log(tk['Nro_Ppto'], st.session_state['user'], f"Estado: {n_est}")
                                st.rerun()

                        with tab3: # Chat robusto
                            df_c, ws_c = fetch_data("Chat_Interno")
                            if not df_c.empty:
                                for _, m in df_c[df_c['Nro_Ppto'].astype(str) == st.session_state.edit_id].iterrows():
                                    st.write(f"*{m['Usuario']}* ({m['Hora']}): {m['Mensaje']}")
                            with st.form("chat_f", clear_on_submit=True):
                                m_text = st.text_input("Escribir mensaje...")
                                if st.form_submit_button("Enviar"):
                                    ws_c.append_row([st.session_state.edit_id, st.session_state['user'], datetime.now().strftime("%H:%M"), m_text])
                                    st.rerun()

                        with tab4:
                            st.download_button("📥 DESCARGAR ORDEN PDF", data=generar_pdf_orden(tk), file_name=f"MAG_{tk['Nro_Ppto']}.pdf", use_container_width=True)
                        
                        if st.button("Cerrar Panel"): del st.session_state.edit_id; st.rerun()

            # Listado de tarjetas
            for _, r in df_p.iterrows():
                saldo = safe_int(r['Monto_Total_Ars']) - safe_int(r['Pagado_Ars'])
                clase = "ticket-card-ok" if saldo <= 0 else "ticket-card"
                st.markdown(f"""
                <div class="{clase}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span class="tag-vendedor">👤 {r['Vendedor']}</span>
                            <h4 style="margin:5px 0;">MAG-{r['Nro_Ppto']} | {r['Cliente']}</h4>
                            <small>📍 {r['Ubicacion']} | 📏 {r['Mts2']} mts²</small>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-size:0.8em; color:#8B949E;">SALDO</div>
                            <div class="monto-highlight">${saldo:,}</div>
                            <div style="background:#0052CC; padding:3px 10px; border-radius:15px; font-size:0.7em;">{r['Estado_Fabricacion']}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Gestionar MAG-{r['Nro_Ppto']}", key=f"edit_{r['Nro_Ppto']}"):
                    st.session_state.edit_id = str(r['Nro_Ppto']); st.rerun()

    elif menu == "📅 SEGUIMIENTO":
        st.title("📅 Seguimiento de Presupuestos")
        with st.expander("➕ Agendar Nuevo Presupuesto", expanded=False):
            with st.form("seg_form"):
                c1, c2, c3 = st.columns(3)
                s_mag = c1.text_input("MAG#")
                s_cli = c2.text_input("Cliente")
                s_ven = c3.selectbox("Vendedor", ["Jonathan", "Martin", "Jacqueline"])
                c4, c5, c6 = st.columns(3)
                s_tel = c4.text_input("WhatsApp (Ej: 54911...)")
                s_ubi = c5.text_input("Ubicación")
                s_mts = c6.number_input("Superficie mts2", min_value=0.0)
                s_mon = st.number_input("Monto Cotizado $", min_value=0)
                s_not = st.text_area("Detalles/Notas")
                if st.form_submit_button("AGENDAR"):
                    ws_s.append_row([s_mag, s_cli, s_ven, s_tel, s_ubi, s_mts, s_mon, datetime.now().strftime("%d/%m/%Y"), s_not])
                    st.success("Guardado."); st.rerun()

        if not df_s.empty:
            for i, r in df_s.iterrows():
                st.markdown(f"""
                <div class="ticket-card">
                    <div style="display:flex; justify-content:space-between;">
                        <div>
                            <span class="tag-vendedor">Vendedor: {r['Vendedor']}</span>
                            <h4 style="margin:5px 0;">{r['Nombre']} (MAG-{r['Nro_Ppto']})</h4>
                            <p style="font-size:0.85em;">📝 {r['Notas']}</p>
                        </div>
                        <div style="text-align:right;">
                            <div class="monto-highlight">${r['Monto']:,}</div>
                            <small>📍 {r['Ubicacion']}</small>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c_wa, c_ap = st.columns(2)
                msg = urllib.parse.quote(f"Hola {r['Nombre']}, te contacto de Grupo Magallan por tu ppto...")
                c_wa.markdown(f'<a href="https://wa.me/{r["Telefono"]}?text={msg}" target="_blank"><button style="width:100%; background:#25D366; color:white; padding:8px; border-radius:8px; cursor:pointer;">📱 Enviar WhatsApp</button></a>', unsafe_allow_html=True)
                if c_ap.button("✅ APROBAR Y ENVIAR A PLANTA", key=f"aprob_{i}", use_container_width=True):
                    ws_p.append_row([r['Nro_Ppto'], r['Nombre'], "Esperando", datetime.now().strftime("%d/%m/%Y"), r['Vendedor'], r['Monto'], 0, "sin iva", r['Mts2'], r['Notas'], r['Ubicacion']])
                    ws_s.delete_rows(i + 2)
                    registrar_log(r['Nro_Ppto'], st.session_state['user'], "Aprobado desde Seguimiento")
                    st.success("¡Enviado a Planta!"); st.rerun()

    elif menu == "🆕 NUEVA CARGA":
        st.title("🆕 Carga Directa a Producción")
        with st.form("direct_form"):
            c1, c2, c3 = st.columns(3)
            f_mag = c1.text_input("MAG#")
            f_cli = c2.text_input("Cliente")
            f_ven = c3.selectbox("Vendedor", ["Jonathan", "Martin", "Jacqueline"])
            c4, c5 = st.columns(2)
            f_ubi = c4.text_input("Ubicación de Obra")
            f_mts = c5.number_input("mts2", min_value=0.0)
            f_mon = st.number_input("Monto Total ARS", min_value=0)
            f_det = st.text_area("Materiales y Detalles Técnicos")
            if st.form_submit_button("REGISTRAR ORDEN DE TRABAJO", use_container_width=True):
                ws_p.append_row([f_mag, f_cli, "Esperando", datetime.now().strftime("%d/%m/%Y"), f_ven, f_mon, 0, "sin iva", f_mts, f_det, f_ubi])
                registrar_log(f_mag, st.session_state['user'], "Carga Directa")
                st.balloons(); st.rerun()

    elif menu == "📊 MÉTRICAS":
        st.title("📊 Análisis de Gestión")
        if not df_p.empty:
            fig = px.pie(df_p, values='Monto_Total_Ars', names='Vendedor', title='Ventas Totales por Vendedor', hole=.4, color_discrete_sequence=px.colors.qualitative.Bold)
            st.plotly_chart(fig, use_container_width=True)
            
            fig2 = px.bar(df_p, x='Estado_Fabricacion', y='Nro_Ppto', title='Cantidad de Proyectos por Estado', color='Estado_Fabricacion')
            st.plotly_chart(fig2, use_container_width=True)