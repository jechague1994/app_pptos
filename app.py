import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF
import urllib.parse
import plotly.express as px

# --- 1. CONFIGURACIÓN INICIAL ---
LOGO_URL = "https://r.jina.ai/i/0586f37648354c4193568c07d3967484"
st.set_page_config(page_title="Magallan Ultra", layout="wide", initial_sidebar_state="expanded")

# --- 2. ESTILOS SEGUROS (No rompen los inputs nativos) ---
st.markdown(f"""
    <style>
    /* Estilo exclusivo para las tarjetas, respetando los inputs nativos de Streamlit */
    .ticket-card {{
        background-color: #1E2129;
        border: 1px solid #333842;
        border-left: 6px solid #0052CC;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        color: #E4E6EB;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }}
    .ticket-card-alerta {{
        border-left: 6px solid #FF5630; /* Rojo para inactivos o vencidos */
    }}
    .ticket-card-ok {{
        border-left: 6px solid #36B37E; /* Verde para pagados/terminados */
    }}
    .badge {{
        background-color: #333842; padding: 4px 8px; border-radius: 4px; font-size: 0.8em;
    }}
    .monto-highlight {{ color: #00D2FF; font-weight: bold; font-size: 1.1em; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCIONES NÚCLEO ---
def safe_int(valor):
    try: return int(float(str(valor).replace("$","").replace(".","").strip()))
    except: return 0

def generar_pdf_completo(tk):
    pdf = FPDF()
    pdf.add_page()
    try: pdf.image(LOGO_URL, x=10, y=8, w=45)
    except: 
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "GRUPO MAGALLAN", ln=True)
    pdf.ln(20)
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=f"ORDEN DE TRABAJO: MAG-{tk['Nro_Ppto']}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12)
    pdf.cell(100, 10, txt=f"Cliente: {str(tk['Cliente'])}")
    pdf.cell(100, 10, txt=f"Ubicacion: {str(tk.get('Ubicacion', 'S/D'))}", ln=True)
    
    total = safe_int(tk['Monto_Total_Ars'])
    pagado = safe_int(tk.get('Pagado_Ars', 0))
    saldo = total - pagado
    
    pdf.cell(100, 10, txt=f"Monto Total: ${total}")
    pdf.cell(100, 10, txt=f"Saldo Pendiente: ${saldo}", ln=True)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, txt="Notas Técnicas y Materiales:", ln=True)
    pdf.set_font("Arial", size=11)
    
    # Limpieza estricta para evitar AttributeError
    notas = str(tk['Materiales_Pendientes']).replace('\n', ' ')
    pdf.multi_cell(0, 8, txt=notas)
    return pdf.output(dest='S').encode('latin-1', errors='replace')

@st.cache_resource
def conectar_gs():
    return gspread.authorize(Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    ))

def fetch(sheet_name):
    try:
        sh = conectar_gs().open("Gestion_Magallan")
        ws = sh.worksheet(sheet_name)
        return pd.DataFrame(ws.get_all_records()), ws
    except Exception as e:
        st.error(f"Error conectando a la hoja {sheet_name}: {e}")
        return pd.DataFrame(), None

# --- 4. SISTEMA DE LOGIN ---
if "authenticated" not in st.session_state:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.image(LOGO_URL, width=200)
        st.markdown("### Acceso Magallan Enterprise")
        u = st.selectbox("Operador", ["---", "Jonathan", "Martin", "Jacqueline"])
        p = st.text_input("Contraseña", type="password")
        if st.button("ACCEDER AL SISTEMA", use_container_width=True):
            if u != "---" and str(st.secrets["usuarios"][u]) == p.strip():
                st.session_state.update({"authenticated": True, "user": u})
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
else:
    # --- 5. NAVEGACIÓN LATERAL ---
    st.sidebar.image(LOGO_URL, use_container_width=True)
    st.sidebar.markdown(f"### 👤 {st.session_state['user']}")
    st.sidebar.markdown("---")
    menu = st.sidebar.radio("SISTEMA", ["📋 TABLERO PLANTA", "📅 AGENDA SEGUIMIENTO", "📊 MÉTRICAS", "🆕 NUEVA CARGA"])
    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()

    # ==========================================
    # MÓDULO 1: TABLERO DE PLANTA (CON EDICIÓN DIRECTA)
    # ==========================================
    if menu == "📋 TABLERO PLANTA":
        df, ws = fetch("Proyectos")
        df_h, _ = fetch("Historial")
        
        st.title("📋 Control de Planta")
        filtro = st.text_input("🔍 Buscar por Cliente o MAG#...")
        st.markdown("---")

        # PANEL DE EDICIÓN SUPERIOR (Solo aparece si se presionó el lapicito)
        if "edit_id" in st.session_state:
            tk_edit = df[df['Nro_Ppto'].astype(str) == st.session_state.edit_id].iloc[0]
            st.markdown(f"### 🛠️ Editando: MAG-{st.session_state.edit_id} | {tk_edit['Cliente']}")
            
            tab1, tab2, tab3, tab4 = st.tabs(["💰 Valores", "🏗️ Logística/Planta", "💬 Chat Interno", "📜 Historial"])
            
            # Pestaña Valores
            with tab1:
                with st.form("form_valores"):
                    c1, c2 = st.columns(2)
                    f_monto = c1.number_input("Monto Total ($)", value=safe_int(tk_edit['Monto_Total_Ars']))
                    f_pagado = c2.number_input("Monto Pagado ($)", value=safe_int(tk_edit.get('Pagado_Ars', 0)))
                    f_ubi = st.text_input("Ubicación", value=tk_edit.get('Ubicacion', ''))
                    
                    if st.form_submit_button("Guardar Valores"):
                        row_idx = df[df['Nro_Ppto'].astype(str) == st.session_state.edit_id].index[0] + 2
                        ws.update_cell(row_idx, 6, f_monto)
                        ws.update_cell(row_idx, 7, f_pagado)
                        ws.update_cell(row_idx, 11, f_ubi)
                        fetch("Historial")[1].append_row([st.session_state.edit_id, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state['user'], "Actualización de montos/ubicación"])
                        st.success("Valores actualizados"); st.rerun()
            
            # Pestaña Logística
            with tab2:
                with st.form("form_planta"):
                    f_notas = st.text_area("Materiales Faltantes y Notas Técnicas", value=str(tk_edit['Materiales_Pendientes']))
                    opciones_est = ["Esperando", "Preparacion", "Terminado", "Entregado"]
                    f_estado = st.selectbox("Estado de Fabricación", opciones_est, index=opciones_est.index(tk_edit['Estado_Fabricacion']) if tk_edit['Estado_Fabricacion'] in opciones_est else 0)
                    
                    if st.form_submit_button("Actualizar Planta"):
                        row_idx = df[df['Nro_Ppto'].astype(str) == st.session_state.edit_id].index[0] + 2
                        ws.update_cell(row_idx, 3, f_estado)
                        ws.update_cell(row_idx, 10, f_notas)
                        fetch("Historial")[1].append_row([st.session_state.edit_id, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state['user'], f"Estado cambiado a: {f_estado}"])
                        st.success("Planta actualizada"); st.rerun()

            # Pestaña Chat Interno
            with tab3:
                df_c, ws_c = fetch("Chat_Interno")
                st.markdown("#### Mensajes del Equipo")
                if not df_c.empty:
                    mensajes = df_c[df_c['Nro_Ppto'].astype(str) == st.session_state.edit_id]
                    for _, msg in mensajes.iterrows():
                        st.info(f"*{msg['Usuario']}* ({msg['Fecha_Hora']}): {msg['Mensaje']}")
                
                with st.form("form_chat", clear_on_submit=True):
                    nuevo_msg = st.text_input("Escribe un mensaje para el equipo...")
                    if st.form_submit_button("Enviar Mensaje"):
                        if nuevo_msg:
                            ws_c.append_row([st.session_state.edit_id, st.session_state['user'], datetime.now().strftime("%d/%m/%Y %H:%M"), nuevo_msg])
                            st.rerun()

            # Pestaña Historial
            with tab4:
                if not df_h.empty:
                    historial_tk = df_h[df_h['Nro_Ppto'].astype(str) == st.session_state.edit_id]
                    st.dataframe(historial_tk[['Fecha_Hora', 'Usuario', 'Accion']], use_container_width=True)

            # Botones de Acción Global para el Ticket Editado
            col_pdf, col_cerrar = st.columns(2)
            with col_pdf:
                st.download_button("📄 DESCARGAR PDF OFICIAL", data=generar_pdf_completo(tk_edit), file_name=f"MAG_{st.session_state.edit_id}.pdf", use_container_width=True)
            with col_cerrar:
                if st.button("❌ Cerrar Edición", use_container_width=True):
                    del st.session_state.edit_id
                    st.rerun()
            
            st.markdown("---") # Separador visual del panel de edición

        # RENDERIZADO DE LA LISTA DE TICKETS
        if not df.empty:
            for idx, r in df.iterrows():
                if filtro.lower() in str(r['Cliente']).lower() or filtro.lower() in str(r['Nro_Ppto']).lower():
                    
                    # Lógica de Saldos e Inactividad
                    total = safe_int(r['Monto_Total_Ars'])
                    pagado = safe_int(r.get('Pagado_Ars', 0))
                    saldo = total - pagado
                    
                    is_inactive = False
                    if not df_h.empty:
                        last_act = df_h[df_h['Nro_Ppto'].astype(str) == str(r['Nro_Ppto'])]
                        if not last_act.empty:
                            try:
                                last_date = pd.to_datetime(last_act.iloc[-1]['Fecha_Hora'], dayfirst=True)
                                if datetime.now() - last_date > timedelta(hours=48):
                                    is_inactive = True
                            except: pass

                    clase_css = "ticket-card-alerta" if is_inactive else ("ticket-card-ok" if saldo <= 0 else "ticket-card")
                    alerta_txt = " <span style='color:#FF5630; font-size:0.8em;'>⚠️ Sin actividad (48hs)</span>" if is_inactive else ""

                    # Diseño de la tarjeta
                    st.markdown(f"""
                    <div class="{clase_css}">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <h4 style="margin:0; padding:0;">MAG-{r['Nro_Ppto']} | {r['Cliente']}{alerta_txt}</h4>
                                <span style="color: #A0AABF; font-size: 0.9em;">📍 {r.get('Ubicacion','S/D')} | <span class="badge">{r['Estado_Fabricacion']}</span></span>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 0.85em; color: #A0AABF;">Saldo Pendiente</div>
                                <div class="monto-highlight">${saldo}</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Botón Lápiz justo debajo de la tarjeta alineado a la derecha
                    col_espacio, col_boton = st.columns([10, 2])
                    with col_boton:
                        if st.button(f"✏️ Editar MAG-{r['Nro_Ppto']}", key=f"btn_edit_{r['Nro_Ppto']}_{idx}", use_container_width=True):
                            st.session_state.edit_id = str(r['Nro_Ppto'])
                            st.rerun()

    # ==========================================
    # MÓDULO 2: AGENDA DE SEGUIMIENTO (72hs + Auto Aprobación)
    # ==========================================
    elif menu == "📅 AGENDA SEGUIMIENTO":
        st.title("📅 Seguimiento de Presupuestos")
        df_s, ws_s = fetch("Seguimiento")
        
        # Formulario de Alta
        with st.expander("➕ Cargar Presupuesto para Seguimiento", expanded=False):
            with st.form("form_nuevo_seguimiento"):
                c1, c2 = st.columns(2)
                n_nom = c1.text_input("Nombre del Cliente")
                n_nro = c2.text_input("Nro MAG (Ej: 1050)")
                n_tel = c1.text_input("Teléfono (Código área + Nro, ej: 54911...)")
                n_ubi = c2.text_input("Ubicación / Obra")
                n_mon = st.number_input("Monto Cotizado ($)", min_value=0)
                
                if st.form_submit_button("Agendar"):
                    if n_nom and n_nro:
                        ws_s.append_row([n_nom, n_nro, n_tel, n_ubi, n_mon, datetime.now().strftime("%d/%m/%Y")])
                        st.success("Agendado correctamente."); st.rerun()
                    else:
                        st.error("Nombre y MAG son obligatorios.")

        st.markdown("### 📋 Pendientes de Aprobación")
        if not df_s.empty:
            for i, r in df_s.iterrows():
                try: f_envio = datetime.strptime(str(r['Fecha_Carga']), "%d/%m/%Y")
                except: f_envio = datetime.now()
                
                dias = (datetime.now() - f_envio).days
                css_clase = "ticket-card-alerta" if dias >= 3 else "ticket-card"
                texto_dias = f"<span style='color:#FF5630;'>⚠️ {dias} días sin contactar</span>" if dias >= 3 else f"<span style='color:#A0AABF;'>Hace {dias} días</span>"

                st.markdown(f"""
                <div class="{css_clase}">
                    <div style="display:flex; justify-content:space-between;">
                        <h4 style="margin:0;">{r['Nombre']} (MAG-{r['Nro_Ppto']})</h4>
                        <div class="monto-highlight">${r['Monto']}</div>
                    </div>
                    <p style="margin:5px 0 0 0; color:#E4E6EB;">📍 {r['Ubicacion']} | 📞 {r['Telefono']} | {texto_dias}</p>
                </div>
                """, unsafe_allow_html=True)

                col_wa, col_aprob = st.columns(2)
                with col_wa:
                    mensaje_wa = urllib.parse.quote(f"Hola {r['Nombre']}, te contacto de Grupo Magallan por tu presupuesto de ${r['Monto']}. ¿Pudiste revisarlo?")
                    st.markdown(f'<a href="https://wa.me/{r["Telefono"]}?text={mensaje_wa}" target="_blank" style="text-decoration:none;"><button style="width:100%; background-color:#25D366; color:white; border:none; padding:10px; border-radius:6px; font-weight:bold; cursor:pointer;">📱 Enviar WhatsApp</button></a>', unsafe_allow_html=True)
                
                with col_aprob:
                    if st.button("✅ APROBAR Y PASAR A PLANTA", key=f"btn_aprobar_{i}", use_container_width=True):
                        df_p, ws_p = fetch("Proyectos")
                        ws_p.append_row([r['Nro_Ppto'], r['Nombre'], "Esperando", datetime.now().strftime("%d/%m/%Y"), "", r['Monto'], 0, "sin iva", "", "", r['Ubicacion']])
                        ws_s.delete_rows(i + 2) # i+2 porque pandas indexa desde 0 y Sheets tiene encabezado (fila 1)
                        st.success(f"Presupuesto MAG-{r['Nro_Ppto']} movido a Planta exitosamente.")
                        st.rerun()
        else:
            st.info("No hay presupuestos en seguimiento.")

    # ==========================================
    # MÓDULO 3: MÉTRICAS
    # ==========================================
    elif menu == "📊 MÉTRICAS":
        st.title("📊 Rendimiento del Equipo")
        df_h, _ = fetch("Historial")
        if not df_h.empty:
            fig = px.pie(df_h, names='Usuario', title="Distribución de Acciones en el Sistema", hole=0.4, color_discrete_sequence=px.colors.sequential.Teal)
            st.plotly_chart(fig, use_container_width=True)

    # ==========================================
    # MÓDULO 4: CARGA RÁPIDA (DIRECTO A PLANTA)
    # ==========================================
    elif menu == "🆕 NUEVA CARGA":
        st.title("🆕 Ingreso Directo a Planta")
        with st.form("form_carga_directa"):
            c1, c2 = st.columns(2)
            n_nro = c1.text_input("Nro Presupuesto MAG")
            n_cliente = c2.text_input("Cliente")
            n_ubi = c1.text_input("Localidad / Ubicación")
            n_monto = c2.number_input("Monto Total ($)", min_value=0)
            
            if st.form_submit_button("Cargar Orden de Trabajo", use_container_width=True):
                if n_nro and n_cliente:
                    _, ws_p = fetch("Proyectos")
                    ws_p.append_row([n_nro, n_cliente, "Esperando", datetime.now().strftime("%d/%m/%Y"), "", n_monto, 0, "sin iva", "", "", n_ubi])
                    fetch("Historial")[1].append_row([n_nro, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state['user'], "Creación Directa"])
                    st.success(f"Orden MAG-{n_nro} cargada a planta con éxito.")
                else:
                    st.error("El número MAG y el Cliente son obligatorios.")