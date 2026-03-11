import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date

# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Grupo Magallan | Gestión Unificada", layout="wide")
st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; background-color: #F1F5F9; border-radius: 8px; padding: 10px 20px; 
    }
    .stTabs [aria-selected="true"] { background-color: #1E3A8A !important; color: white !important; }
    .header-box { 
        background-color: #1E3A8A; color: white; padding: 25px; border-radius: 12px; margin-bottom: 25px; 
    }
    .chat-bubble { 
        background: #F8FAFC; padding: 12px; border-radius: 10px; margin-bottom: 8px; border-left: 5px solid #1E3A8A; 
    }
    </style>
    """, unsafe_allow_html=True)

# 2. CONEXIÓN (Basada en tu Sheet actual)
@st.cache_resource
def conectar():
    return gspread.authorize(Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    ))

def traer_pestaña(nombre):
    sh = conectar().open("Gestion_Magallan")
    df = pd.DataFrame(sh.worksheet(nombre).get_all_records())
    return df, sh.worksheet(nombre)

# 3. LOGIN
if "authenticated" not in st.session_state:
    st.title("🏗️ Grupo Magallan | Acceso")
    u = st.selectbox("Usuario", ["---"] + list(st.secrets["usuarios"].keys()))
    p = st.text_input("Contraseña", type="password")
    if st.button("INGRESAR"):
        if u != "---" and str(st.secrets["usuarios"][u]).strip() == p.strip():
            st.session_state.update({"authenticated": True, "user": u})
            st.rerun()
else:
    # --- PANTALLA PRINCIPAL: BUSCADOR ---
    df_p, ws_p = traer_pestaña("Proyectos")
    
    st.sidebar.title(f"👤 {st.session_state['user']}")
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["authenticated"]
        st.rerun()

    st.title("📂 Buscador de Presupuestos")
    
    # Selector unificado
    lista_obras = ["---"] + [f"{r['Nro_Ppto']} - {r['Cliente']}" for _, r in df_p.iterrows()]
    seleccion = st.selectbox("Seleccione una obra para gestionar:", lista_obras)

    if seleccion != "---":
        nro_sel = str(seleccion.split(" - ")[0])
        obra = df_p[df_p['Nro_Ppto'].astype(str) == nro_sel].iloc[0]

        # ENCABEZADO DINÁMICO
        st.markdown(f"""
            <div class="header-box">
                <h2 style='margin:0;'>📋 Presupuesto #{nro_sel}</h2>
                <p style='margin:0; opacity:0.9;'>Cliente: {obra['Cliente']} | Monto: ${obra['Monto_Total_Ars']} | IVA: {obra['IVA']}</p>
            </div>
        """, unsafe_allow_html=True)

        # PANEL DE TRABAJO (TABS)
        t_fab, t_log, t_chat, t_hist = st.tabs(["🏗️ Planta", "🚚 Logística", "💬 Chat", "📜 Historial"])

        with t_fab:
            st.subheader("Control de Fabricación")
            with st.form("form_planta"):
                est_actual = st.selectbox("Estado en Planta:", ["Esperando", "Preparacion", "Terminado", "Entregado"], 
                                        index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(obra['Estado_Fabricacion']))
                notas = st.text_area("Materiales Pendientes:", value=obra['Materiales_Pendientes'])
                if st.form_submit_button("Actualizar Planta"):
                    fila = df_p[df_p['Nro_Ppto'].astype(str) == nro_sel].index[0] + 2
                    ws_p.update_cell(fila, 3, est_actual) # Estado_Fabricacion
                    ws_p.update_cell(fila, 10, notas)     # Materiales_Pendientes
                    
                    # Registro automático en Historial
                    _, ws_h = traer_pestaña("Historial")
                    ws_h.append_row([nro_sel, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state['user'], f"Cambio a {est_actual}"])
                    st.success("Planta actualizada con éxito")
                    st.rerun()

        with t_log:
            st.subheader("Datos de Instalación")
            df_l, ws_l = traer_pestaña("Logistica")
            log_obra = df_l[df_l['Nro_Ppto'].astype(str) == nro_sel]
            
            with st.form("form_log"):
                tec = st.text_input("Técnico Asignado:", value=log_obra.iloc[0]['Tecnicos'] if not log_obra.empty else "")
                f_ins = st.text_input("Fecha Instalación (DD/MM/YYYY):", value=log_obra.iloc[0]['Fecha_Instalacion'] if not log_obra.empty else "")
                est_log = st.selectbox("Estado Entrega:", ["Pendiente", "Esperando", "Terminado"], 
                                     index=0 if log_obra.empty else ["Pendiente", "Esperando", "Terminado"].index(log_obra.iloc[0]['Estado_Entrega']))
                
                if st.form_submit_button("Guardar Logística"):
                    if not log_obra.empty:
                        fila_l = log_obra.index[0] + 2
                        ws_l.update_cell(fila_l, 2, tec) # Col B: Tecnicos
                        ws_l.update_cell(fila_l, 3, f_ins) # Col C: Fecha_Instalacion
                        ws_l.update_cell(fila_l, 4, est_log) # Col D: Estado_Entrega
                    else:
                        ws_l.append_row([nro_sel, tec, f_ins, est_log])
                    st.success("Datos de logística guardados")
                    st.rerun()

        with t_chat:
            st.subheader("Chat del Proyecto")
            df_c, ws_c = traer_pestaña("Chat_Interno")
            mensajes = df_c[df_c['Nro_Ppto'].astype(str) == nro_sel]
            
            with st.form("form_chat", clear_on_submit=True):
                nuevo_msg = st.text_area("Escribir mensaje:")
                if st.form_submit_button("Enviar"):
                    ws_c.append_row([nro_sel, st.session_state['user'], datetime.now().strftime("%d/%m/%Y %H:%M"), nuevo_msg])
                    st.rerun()
            
            for _, m in mensajes.iloc[::-1].iterrows():
                st.markdown(f"<div class='chat-bubble'><b>{m['Usuario']}</b> ({m['Fecha_Hora']}):<br>{m['Mensaje']}</div>", unsafe_allow_html=True)

        with t_hist:
            st.subheader("Historial de Movimientos")
            df_h, _ = traer_pestaña("Historial")
            hist_filtrado = df_h[df_h['Nro_Ppto'].astype(str) == nro_sel]
            st.table(hist_filtrado[['Fecha_Hora', 'Usuario', 'Detalle']])

    else:
        # PANTALLA DE INICIO: OPCIÓN DE CARGA NUEVA
        st.info("Seleccione un presupuesto arriba para ver los detalles o cree uno nuevo aquí:")
        with st.expander("➕ Cargar Nuevo Presupuesto"):
            with st.form("nuevo_ppto"):
                c1, c2 = st.columns(2)
                v_nro = c1.text_input("Nro_Ppto:")
                v_cli = c2.text_input("Cliente:")
                v_mon = c1.number_input("Monto Total ($):", min_value=0)
                v_iva = c2.selectbox("IVA:", ["sin iva", "iva 10.5%", "iva 21%"])
                if st.form_submit_button("Crear Proyecto"):
                    ws_p.append_row([v_nro, v_cli, "Esperando", date.today().strftime("%d/%m/%Y"), "", v_mon, 0, v_iva, "", ""])
                    st.success("¡Proyecto creado!")
                    st.rerun()