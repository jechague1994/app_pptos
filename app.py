import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import plotly.express as px

# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Grupo Magallan | Sistema Total", layout="wide")
st.markdown("""
    <style>
    html, body, [class*="st-"] { font-size: 1.05rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 15px; }
    .stTabs [data-baseweb="tab"] { height: 45px; background-color: #F1F5F9; border-radius: 5px; }
    .stTabs [aria-selected="true"] { background-color: #1E3A8A !important; color: white !important; }
    .header-box { background-color: #1E3A8A; color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
    .card-alerta { background-color: #FEF2F2; border-left: 5px solid #EF4444; padding: 10px; color: #991B1B; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# 2. CONEXIÓN Y FUNCIONES DE DATOS
@st.cache_resource
def conectar():
    return gspread.authorize(Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    ))

def traer_datos(pestaña):
    sh = conectar().open("Gestion_Magallan")
    ws = sh.worksheet(pestaña)
    df = pd.DataFrame(ws.get_all_records())
    return df, ws

# 3. SEGURIDAD
if "authenticated" not in st.session_state:
    st.title("🏗️ Grupo Magallan | Acceso")
    u = st.selectbox("Usuario", ["---"] + list(st.secrets["usuarios"].keys()))
    p = st.text_input("Contraseña", type="password")
    if st.button("INGRESAR"):
        if u != "---" and str(st.secrets["usuarios"][u]).strip() == p.strip():
            st.session_state.update({"authenticated": True, "user": u})
            st.rerun()
else:
    # --- MENÚ LATERAL ---
    st.sidebar.title(f"👤 {st.session_state['user']}")
    menu = st.sidebar.radio("IR A:", ["📂 GESTIÓN POR PPTO", "📈 ESTADÍSTICAS", "🆕 NUEVO PROYECTO"])
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["authenticated"]
        st.rerun()

    # --- A. GESTIÓN POR PRESUPUESTO (EDICIÓN TOTAL) ---
    if menu == "📂 GESTIÓN POR PPTO":
        df_p, ws_p = traer_datos("Proyectos")
        st.title("📂 Buscador y Edición de Obra")
        
        lista = ["---"] + [f"{r['Nro_Ppto']} - {r['Cliente']}" for _, r in df_p.iterrows()]
        sel = st.selectbox("Seleccione Presupuesto:", lista)

        if sel != "---":
            nro_sel = str(sel.split(" - ")[0])
            obra = df_p[df_p['Nro_Ppto'].astype(str) == nro_sel].iloc[0]

            # Alerta de Vencimiento
            try:
                f_ent = pd.to_datetime(obra['Fecha_Entrega'], dayfirst=True).date()
                if f_ent < date.today() and obra['Estado_Fabricacion'] != "Entregado":
                    st.markdown(f"<div class='card-alerta'>⚠️ ATENCIÓN: Esta obra tiene fecha de entrega vencida ({obra['Fecha_Entrega']})</div>", unsafe_allow_html=True)
            except: pass

            st.markdown(f"<div class='header-box'><h2>📋 Ppto #{nro_sel} | {obra['Cliente']}</h2></div>", unsafe_allow_html=True)

            t1, t2, t3, t4 = st.tabs(["✏️ EDITAR VALORES", "🏗️ PLANTA", "🚚 LOGÍSTICA", "💬 CHAT/HISTORIAL"])

            with t1:
                st.subheader("Modificar Datos del Presupuesto")
                with st.form("form_valores"):
                    c1, c2 = st.columns(2)
                    new_cli = c1.text_input("Nombre Cliente", value=obra['Cliente'])
                    new_mon = c2.number_input("Monto Total (Ars)", value=int(obra['Monto_Total_Ars']))
                    new_iva = c1.selectbox("IVA", ["sin iva", "iva 10.5%", "iva 21%"], 
                                         index=["sin iva", "iva 10.5%", "iva 21%"].index(str(obra['IVA']).lower()))
                    if st.form_submit_button("GUARDAR CAMBIOS DE VALOR"):
                        idx = df_p[df_p['Nro_Ppto'].astype(str) == nro_sel].index[0] + 2
                        ws_p.update_cell(idx, 2, new_cli) # Col B
                        ws_p.update_cell(idx, 6, new_mon) # Col F
                        ws_p.update_cell(idx, 8, new_iva) # Col H
                        # Registro
                        _, ws_h = traer_datos("Historial")
                        ws_h.append_row([nro_sel, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state['user'], f"Editó valores: ${new_mon}"])
                        st.success("Valores actualizados")
                        st.rerun()

            with t2:
                st.subheader("Gestión de Fabricación")
                with st.form("form_fab"):
                    est = st.selectbox("Estado:", ["Esperando", "Preparacion", "Terminado", "Entregado"], 
                                     index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(obra['Estado_Fabricacion']))
                    mat = st.text_area("Materiales/Notas:", value=obra['Materiales_Pendientes'])
                    if st.form_submit_button("ACTUALIZAR PLANTA"):
                        idx = df_p[df_p['Nro_Ppto'].astype(str) == nro_sel].index[0] + 2
                        ws_p.update_cell(idx, 3, est) # Col C
                        ws_p.update_cell(idx, 10, mat) # Col J
                        _, ws_h = traer_datos("Historial")
                        ws_h.append_row([nro_sel, datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state['user'], f"Cambio estado a {est}"])
                        st.success("Estado en planta guardado")
                        st.rerun()

            with t3:
                st.subheader("Logística e Instalación")
                df_l, ws_l = traer_datos("Logistica")
                log = df_l[df_l['Nro_Ppto'].astype(str) == nro_sel]
                with st.form("form_log"):
                    t_inc = st.text_input("Técnico:", value=log.iloc[0]['Tecnicos'] if not log.empty else "")
                    f_inc = st.text_input("Fecha (DD/MM/YYYY):", value=log.iloc[0]['Fecha_Instalacion'] if not log.empty else "")
                    if st.form_submit_button("GUARDAR LOGÍSTICA"):
                        if not log.empty:
                            fila_l = log.index[0] + 2
                            ws_l.update_cell(fila_l, 2, t_inc)
                            ws_l.update_cell(fila_l, 3, f_inc)
                        else:
                            ws_l.append_row([nro_sel, t_inc, f_inc, "Pendiente"])
                        st.success("Logística guardada")
                        st.rerun()

            with t4:
                df_c, ws_c = traer_datos("Chat_Interno")
                st.subheader("Historial y Notas")
                with st.form("f_chat", clear_on_submit=True):
                    msg = st.text_input("Agregar nota/mensaje:")
                    if st.form_submit_button("Enviar"):
                        ws_c.append_row([nro_sel, st.session_state['user'], datetime.now().strftime("%d/%m/%Y %H:%M"), msg])
                        st.rerun()
                
                # Mostrar chat e historial unidos
                df_h, _ = traer_datos("Historial")
                comb = pd.concat([
                    mensajes := df_c[df_c['Nro_Ppto'].astype(str) == nro_sel].rename(columns={'Mensaje': 'Accion'}),
                    hist := df_h[df_h['Nro_Ppto'].astype(str) == nro_sel].rename(columns={'Detalle': 'Accion'})
                ]).sort_values('Fecha_Hora', ascending=False)
                st.table(comb[['Fecha_Hora', 'Usuario', 'Accion']])

    # --- B. ESTADÍSTICAS POR USUARIO ---
    elif menu == "📈 ESTADÍSTICAS":
        st.title("📈 Rendimiento de Equipo")
        df_h, _ = traer_datos("Historial")
        if not df_h.empty:
            df_h['f_dt'] = pd.to_datetime(df_h['Fecha_Hora'], dayfirst=True, errors='coerce').dt.date
            c1, c2 = st.columns(2)
            f_i = c1.date_input("Desde", date(2025, 1, 1))
            f_f = c2.date_input("Hasta", date.today())
            
            df_f = df_h[(df_h['f_dt'] >= f_i) & (df_h['f_dt'] <= f_f)].dropna(subset=['f_dt'])
            
            st.plotly_chart(px.bar(df_f['Usuario'].value_counts().reset_index(), 
                                  x='Usuario', y='count', title="Acciones totales por usuario"), use_container_width=True)
            st.subheader("Detalle de movimientos")
            st.dataframe(df_f[['Nro_Ppto', 'Fecha_Hora', 'Usuario', 'Detalle']], use_container_width=True)

    # --- C. NUEVO PROYECTO ---
    elif menu == "🆕 NUEVO PROYECTO":
        st.title("🆕 Carga de Obra")
        with st.form("alta"):
            c1, c2 = st.columns(2)
            n_n = c1.text_input("Número Ppto:")
            n_c = c2.text_input("Cliente:")
            n_m = c1.number_input("Monto Ars:", min_value=0)
            n_i = c2.selectbox("IVA:", ["sin iva", "iva 10.5%", "iva 21%"])
            if st.form_submit_button("CREAR PROYECTO"):
                _, ws_p = traer_datos("Proyectos")
                ws_p.append_row([n_n, n_c, "Esperando", date.today().strftime("%d/%m/%Y"), "", n_m, 0, n_i, "", ""])
                st.success("Proyecto creado. Búscalo en GESTIÓN POR PPTO.")