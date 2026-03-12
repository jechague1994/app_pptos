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

# --- 2. ESTILOS SEGUROS ---
st.markdown(f"""
    <style>
    .ticket-card {{ background-color: #1E2129; border: 1px solid #333842; border-left: 6px solid #0052CC; border-radius: 8px; padding: 16px; margin-bottom: 12px; color: #E4E6EB; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
    .ticket-card-alerta {{ background-color: #1E2129; border: 1px solid #333842; border-left: 6px solid #FF5630; border-radius: 8px; padding: 16px; margin-bottom: 12px; color: #E4E6EB; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
    .ticket-card-ok {{ background-color: #1E2129; border: 1px solid #333842; border-left: 6px solid #36B37E; border-radius: 8px; padding: 16px; margin-bottom: 12px; color: #E4E6EB; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
    .badge {{ background-color: #333842; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }}
    .monto-highlight {{ color: #00D2FF; font-weight: bold; font-size: 1.1em; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCIONES NÚCLEO ---
def safe_int(valor):
    try: return int(float(str(valor).replace("$","").replace(".","").strip()))
    except: return 0

def registrar_historial(nro, user, accion):
    _, ws_h = fetch("Historial")
    if ws_h is not None:
        try: ws_h.append_row([str(nro), datetime.now().strftime("%d/%m/%Y %H:%M"), user, accion])
        except: pass

def generar_pdf_completo(tk):
    pdf = FPDF()
    pdf.add_page()
    # Encabezado tolerante a fallos de red con la imagen
    try: 
        pdf.image(LOGO_URL, x=10, y=8, w=45)
    except: 
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, "GRUPO MAGALLAN", 0, 1, 'L')
    pdf.ln(20)
    
    pdf.set_font("Arial", 'B', 16)
    nro = tk.get('Nro_Ppto', 'S/D')
    pdf.cell(200, 10, f"ORDEN DE TRABAJO: MAG-{nro}", 0, 1, 'C')
    pdf.ln(10)
    
    # Textos forzados a str() para evitar el AttributeError
    pdf.set_font("Arial", size=12)
    cliente = str(tk.get('Cliente', 'S/D'))
    ubi = str(tk.get('Ubicacion', 'S/D'))
    pdf.cell(100, 10, f"Cliente: {cliente}")
    pdf.cell(100, 10, f"Ubicacion: {ubi}", 0, 1)
    
    total = safe_int(tk.get('Monto_Total_Ars', 0))
    pagado = safe_int(tk.get('Pagado_Ars', 0))
    saldo = total - pagado
    
    pdf.cell(100, 10, f"Monto Total: ${total}")
    pdf.cell(100, 10, f"Saldo Pendiente: ${saldo}", 0, 1)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(200, 10, "Notas Tecnicas y Materiales:", 0, 1)
    pdf.set_font("Arial", size=11)
    
    notas = str(tk.get('Materiales_Pendientes', '')).replace('\n', ' ')
    if not notas.strip(): notas = "Sin notas tecnicas registradas."
    pdf.multi_cell(0, 8, notas)
    
    return pdf.output(dest='S').encode('latin-1', errors='replace')

@st.cache_resource(ttl=600)
def conectar_gs():
    return gspread.authorize(Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    ))

def fetch(sheet_name):
    try:
        sh = conectar_gs().open("Gestion_Magallan")
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        if not df.empty:
            df = df.fillna("") # VITAL: Convierte celdas vacías/NaN en strings para evitar cuelgues
        return df, ws
    except Exception as e:
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
        if st.button("INICIAR SESIÓN", use_container_width=True):
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
    # MÓDULO 1: TABLERO DE PLANTA
    # ==========================================
    if menu == "📋 TABLERO PLANTA":
        df, ws = fetch("Proyectos")
        df_h, _ = fetch("Historial")
        
        st.title("📋 Control de Planta")
        filtro = st.text_input("🔍 Buscar por Cliente o MAG#...")
        st.markdown("---")

        # PANEL DE EDICIÓN SUPERIOR (Con validaciones de seguridad)
        if "edit_id" in st.session_state:
            if not df.empty and st.session_state.edit_id in df['Nro_Ppto'].astype(str).values:
                tk_edit = df[df['Nro_Ppto'].astype(str) == st.session_state.edit_id].iloc[0]
                st.markdown(f"### 🛠️ Editando: MAG-{st.session_state.edit_id} | {tk_edit.get('Cliente', '')}")
                
                tab1, tab2, tab3, tab4 = st.tabs(["💰 Valores", "🏗️ Logística/Planta", "💬 Chat Interno", "📜 Historial"])
                
                with tab1:
                    with st.form("form_valores"):
                        c1, c2 = st.columns(2)
                        f_monto = c1.number_input("Monto Total (ARS)", value=safe_int(tk_edit.get('Monto_Total_Ars', 0)))
                        f_pagado = c2.number_input("Monto Pagado (ARS)", value=safe_int(tk_edit.get('Pagado_Ars', 0)))
                        f_ubi = st.text_input("Ubicación", value=tk_edit.get('Ubicacion', ''))
                        
                        if st.form_submit_button("Guardar Valores"):
                            if ws is not None:
                                row_idx = df[df['Nro_Ppto'].astype(str) == st.session_state.edit_id].index[0] + 2
                                ws.update_cell(row_idx, 6, f_monto)
                                ws.update_cell(row_idx, 7, f_pagado)
                                ws.update_cell(row_idx, 11, f_ubi)
                                registrar_historial(st.session_state.edit_id, st.session_state['user'], "Actualización de montos/ubicación")
                                st.success("Valores actualizados"); st.rerun()
                            else: st.error("Error conectando a Sheets.")
                
                with tab2:
                    with st.form("form_planta"):
                        f_notas = st.text_area("Materiales Faltantes y Notas Técnicas", value=str(tk_edit.get('Materiales_Pendientes', '')))
                        estado_actual = tk_edit.get('Estado_Fabricacion', 'Esperando')
                        opciones_est = ["Esperando", "Preparacion", "Terminado", "Entregado"]
                        idx_est = opciones_est.index(estado_actual) if estado_actual in opciones_est else 0
                        f_estado = st.selectbox("Estado de Fabricación", opciones_est, index=idx_est)
                        
                        if st.form_submit_button("Actualizar Planta"):
                            if ws is not None:
                                row_idx = df[df['Nro_Ppto'].astype(str) == st.session_state.edit_id].index[0] + 2
                                ws.update_cell(row_idx, 3, f_estado)
                                ws.update_cell(row_idx, 10, f_notas)
                                registrar_historial(st.session_state.edit_id, st.session_state['user'], f"Estado cambiado a: {f_estado}")
                                st.success("Planta actualizada"); st.rerun()
                            else: st.error("Error conectando a Sheets.")

                with tab3:
                    df_c, ws_c = fetch("Chat_Interno")
                    st.markdown("#### Mensajes del Equipo")
                    if not df_c.empty and 'Nro_Ppto' in df_c.columns and 'Mensaje' in df_c.columns:
                        mensajes = df_c[df_c['Nro_Ppto'].astype(str) == st.session_state.edit_id]
                        for _, msg in mensajes.iterrows():
                            st.info(f"*{msg.get('Usuario','?')}* ({msg.get('Fecha_Hora','')}): {msg['Mensaje']}")
                    else: st.caption("No hay mensajes todavía para esta orden.")
                    
                    with st.form("form_chat", clear_on_submit=True):
                        nuevo_msg = st.text_input("Escribe un mensaje...")
                        if st.form_submit_button("Enviar Mensaje"):
                            if nuevo_msg and ws_c is not None:
                                ws_c.append_row([st.session_state.edit_id, st.session_state['user'], datetime.now().strftime("%d/%m/%Y %H:%M"), nuevo_msg])
                                st.rerun()

                with tab4:
                    if not df_h.empty and 'Fecha_Hora' in df_h.columns and 'Accion' in df_h.columns:
                        historial_tk = df_h[df_h['Nro_Ppto'].astype(str) == st.session_state.edit_id]
                        st.dataframe(historial_tk[['Fecha_Hora', 'Usuario', 'Accion']], use_container_width=True)
                    else: st.info("Historial vacío o en inicialización.")

                col_pdf, col_cerrar = st.columns(2)
                with col_pdf:
                    st.download_button("📄 DESCARGAR PDF OFICIAL", data=generar_pdf_completo(tk_edit), file_name=f"MAG_{st.session_state.edit_id}.pdf", use_container_width=True)
                with col_cerrar:
                    if st.button("❌ Cerrar Edición", use_container_width=True):
                        del st.session_state.edit_id
                        st.rerun()
                
                st.markdown("---")
            else:
                st.warning("El ticket seleccionado ya no se encuentra en la base de datos.")
                if st.button("Limpiar selección"): 
                    del st.session_state.edit_id
                    st.rerun()

        # RENDERIZADO DE LA LISTA DE TICKETS (A prueba de fallos)
        if not df.empty:
            for idx, r in df.iterrows():
                cliente = str(r.get('Cliente', ''))
                nro = str(r.get('Nro_Ppto', ''))
                if filtro.lower() in cliente.lower() or filtro.lower() in nro.lower():
                    
                    total = safe_int(r.get('Monto_Total_Ars', 0))
                    pagado = safe_int(r.get('Pagado_Ars', 0))
                    saldo = total - pagado
                    
                    is_inactive = False
                    if not df_h.empty and 'Nro_Ppto' in df_h.columns and 'Fecha_Hora' in df_h.columns:
                        last_act = df_h[df_h['Nro_Ppto'].astype(str) == nro]
                        if not last_act.empty:
                            try:
                                last_date = pd.to_datetime(last_act.iloc[-1]['Fecha_Hora'], dayfirst=True)
                                if datetime.now() - last_date > timedelta(hours=48):
                                    is_inactive = True
                            except: pass

                    clase_css = "ticket-card-alerta" if is_inactive else ("ticket-card-ok" if saldo <= 0 else "ticket-card")
                    alerta_txt = " <span style='color:#FF5630; font-size:0.8em;'>⚠️ Sin Actividad</span>" if is_inactive else ""

                    st.markdown(f"""
                    <div class="{clase_css}">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <h4 style="margin:0; padding:0;">MAG-{nro} | {cliente}{alerta_txt}</h4>
                                <span style="color: #A0AABF; font-size: 0.9em;">📍 {r.get('Ubicacion','S/D')} | <span class="badge">{r.get('Estado_Fabricacion','S/D')}</span></span>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 0.85em; color: #A0AABF;">Saldo Pendiente</div>
                                <div class="monto-highlight">${saldo}</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_espacio, col_boton = st.columns([10, 2])
                    with col_boton:
                        # Clave única obligatoria para StreamlitDuplicateElementKey
                        if st.button(f"✏️ Editar MAG-{nro}", key=f"btn_edit_{nro}_{idx}", use_container_width=True):
                            st.session_state.edit_id = nro
                            st.rerun()
        else:
            st.info("No hay órdenes de trabajo cargadas en la hoja 'Proyectos'.")

    # ==========================================
    # MÓDULO 2: AGENDA DE SEGUIMIENTO
    # ==========================================
    elif menu == "📅 AGENDA SEGUIMIENTO":
        st.title("📅 Seguimiento de Presupuestos")
        df_s, ws_s = fetch("Seguimiento")
        
        with st.expander("➕ Cargar Presupuesto para Seguimiento", expanded=False):
            with st.form("form_nuevo_seguimiento"):
                c1, c2 = st.columns(2)
                n_nom = c1.text_input("Nombre del Cliente")
                n_nro = c2.text_input("Nro MAG (Ej: 1050)")
                n_tel = c1.text_input("Teléfono (Código área + Nro)")
                n_ubi = c2.text_input("Ubicación / Obra")
                n_mts = c1.number_input("Superficie Aprox (mts2)", min_value=0.0, step=0.1)
                n_mon = c2.number_input("Monto Cotizado (ARS)", min_value=0)
                
                if st.form_submit_button("Agendar"):
                    if n_nom and n_nro and ws_s is not None:
                        ws_s.append_row([n_nom, n_nro, n_tel, n_ubi, n_mon, datetime.now().strftime("%d/%m/%Y"), n_mts])
                        st.success("Agendado correctamente."); st.rerun()
                    elif ws_s is None:
                        st.error("Error crítico: Verifique que la hoja se llame exactamente 'Seguimiento' en Google Sheets.")
                    else:
                        st.error("Nombre y MAG son obligatorios.")

        st.markdown("### 📋 Pendientes de Aprobación")
        if not df_s.empty:
            for i, r in df_s.iterrows():
                try: f_envio = datetime.strptime(str(r.get('Fecha_Carga', datetime.now().strftime("%d/%m/%Y"))), "%d/%m/%Y")
                except: f_envio = datetime.now()
                
                dias = (datetime.now() - f_envio).days
                css_clase = "ticket-card-alerta" if dias >= 3 else "ticket-card"
                texto_dias = f"<span style='color:#FF5630;'>⚠️ {dias} días sin contactar</span>" if dias >= 3 else f"<span style='color:#A0AABF;'>Hace {dias} días</span>"

                st.markdown(f"""
                <div class="{css_clase}">
                    <div style="display:flex; justify-content:space-between;">
                        <h4 style="margin:0;">{r.get('Nombre','')} (MAG-{r.get('Nro_Ppto','')})</h4>
                        <div class="monto-highlight">${r.get('Monto',0)}</div>
                    </div>
                    <p style="margin:5px 0 0 0; color:#E4E6EB;">📍 {r.get('Ubicacion','')} | 📞 {r.get('Telefono','')} | {texto_dias}</p>
                </div>
                """, unsafe_allow_html=True)

                col_wa, col_aprob = st.columns(2)
                with col_wa:
                    mensaje_wa = urllib.parse.quote(f"Hola {r.get('Nombre','')}, te contacto de Grupo Magallan por tu presupuesto de ${r.get('Monto',0)}. ¿Pudiste revisarlo?")
                    st.markdown(f'<a href="https://wa.me/{r.get("Telefono","")}?text={mensaje_wa}" target="_blank" style="text-decoration:none;"><button style="width:100%; background-color:#25D366; color:white; border:none; padding:10px; border-radius:6px; font-weight:bold; cursor:pointer;">📱 Enviar WhatsApp</button></a>', unsafe_allow_html=True)
                
                with col_aprob:
                    if st.button("✅ APROBAR Y PASAR A PLANTA", key=f"btn_aprobar_{r.get('Nro_Ppto','')}_{i}", use_container_width=True):
                        df_p, ws_p = fetch("Proyectos")
                        if ws_p is not None and ws_s is not None:
                            ws_p.append_row([r.get('Nro_Ppto',''), r.get('Nombre',''), "Esperando", datetime.now().strftime("%d/%m/%Y"), "", r.get('Monto',0), 0, "sin iva", "", "", r.get('Ubicacion','')])
                            ws_s.delete_rows(i + 2)
                            registrar_historial(r.get('Nro_Ppto',''), st.session_state['user'], "Aprobado desde Agenda")
                            st.success(f"Presupuesto movido a Planta exitosamente.")
                            st.rerun()
                        else:
                            st.error("Fallo de conexión. Revise Google Sheets.")
        else:
            st.info("No hay presupuestos en seguimiento.")

    # ==========================================
    # MÓDULO 3: MÉTRICAS
    # ==========================================
    elif menu == "📊 MÉTRICAS":
        st.title("📊 Rendimiento del Equipo")
        df_h, _ = fetch("Historial")
        if not df_h.empty and 'Usuario' in df_h.columns:
            fig = px.pie(df_h, names='Usuario', title="Distribución de Acciones en el Sistema", hole=0.4, color_discrete_sequence=px.colors.sequential.Teal)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aún no hay suficientes datos registrados en el historial para generar la torta de métricas.")

    # ==========================================
    # MÓDULO 4: CARGA RÁPIDA
    # ==========================================
    elif menu == "🆕 NUEVA CARGA":
        st.title("🆕 Ingreso Directo a Planta")
        with st.form("form_carga_directa"):
            c1, c2 = st.columns(2)
            n_nro = c1.text_input("Nro Presupuesto MAG")
            n_cliente = c2.text_input("Cliente")
            n_ubi = c1.text_input("Localidad / Ubicación")
            n_monto = c2.number_input("Monto Total (ARS)", min_value=0)
            n_mts = c1.number_input("Superficie Total (mts2)", min_value=0.0, step=0.1)
            
            if st.form_submit_button("Cargar Orden de Trabajo", use_container_width=True):
                if n_nro and n_cliente:
                    _, ws_p = fetch("Proyectos")
                    if ws_p is not None:
                        ws_p.append_row([n_nro, n_cliente, "Esperando", datetime.now().strftime("%d/%m/%Y"), "", n_monto, 0, "sin iva", "", "", n_ubi])
                        registrar_historial(n_nro, st.session_state['user'], "Creación Directa")
                        st.success(f"Orden MAG-{n_nro} cargada a planta con éxito.")
                    else:
                        st.error("No se pudo conectar con la hoja 'Proyectos'.")
                else:
                    st.error("El número MAG y el Cliente son obligatorios.")