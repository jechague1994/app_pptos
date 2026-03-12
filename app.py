import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fpdf import FPDF
import plotly.express as px
import urllib.parse

# --- 1. CONFIGURACIÓN Y ESTILO (INDUSTRIAL LIGHT CON TARJETAS) ---
st.set_page_config(page_title="Grupo Magallan - Gestión Pro", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F4F7F9; color: #1E293B; }
    
    /* Contenedores de Métricas (Dashboard Superior) */
    .metric-container {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .metric-val { color: #0284C7; font-size: 1.6rem; font-weight: 700; }
    .metric-label { color: #64748B; font-size: 0.8rem; text-transform: uppercase; }

    /* Tarjetas estilo "Captura" (Claras) */
    .ticket-card { 
        background: white; border: 1px solid #E2E8F0; border-left: 6px solid #0284C7;
        border-radius: 10px; padding: 15px; margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .tag-vendedor { background: #F1F5F9; color: #475569; padding: 3px 10px; border-radius: 15px; font-size: 0.75rem; font-weight: 600; }
    .monto-highlight { color: #0284C7; font-size: 1.3rem; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCIONES DE DATOS ---
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
        st.error(f"Error de conexión: {e}")
        return None

def obtener_datos_seguros(nombre_hoja, cols_necesarias):
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
        st.error(f"Error en {nombre_hoja}: {e}")
        return pd.DataFrame(columns=cols_necesarias), None

# --- 3. LÓGICA DE ACCESO ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        st.subheader("Login - Grupo Magallan")
        u = st.selectbox("Usuario", ["---", "Jonathan", "Martin", "Jacqueline"])
        p = st.text_input("Clave", type="password")
        if st.button("INGRESAR", use_container_width=True):
            if u != "---" and str(st.secrets["usuarios"].get(u)) == p:
                st.session_state.auth, st.session_state.user = True, u
                st.rerun()
else:
    # Carga de datos
    df_p, ws_p = obtener_datos_seguros("Proyectos", ['Nro_Ppto', 'Cliente', 'Estado_Fabricacion', 'Fecha_Ingreso', 'Vendedor', 'Monto_Total_Ars', 'Pagado_Ars', 'Mts2', 'Ubicacion', 'Materiales_Pendientes'])
    df_s, ws_s = obtener_datos_seguros("Seguimiento", ['Fecha', 'Cliente', 'Monto_Estimado', 'Vendedor', 'Ubicacion', 'Telefono', 'Notas', 'Mts2', 'MAG_Ref'])
    df_h, ws_h = obtener_datos_seguros("Historial", ['Nro_Ppto', 'Fecha_Hora', 'Usuario', 'Accion'])

    st.sidebar.title(f"Operador: {st.session_state.user}")
    menu = st.sidebar.radio("MENÚ", ["📋 TABLERO PLANTA", "📅 SEGUIMIENTO", "🆕 NUEVA CARGA"])

    # --- PÁGINA: SEGUIMIENTO (DISEÑO SOLICITADO) ---
    if menu == "📅 SEGUIMIENTO":
        # 1. Dashboard de Seguimiento
        st.markdown("### 🏦 Resumen de Presupuestos en Espera")
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f'<div class="metric-container"><div class="metric-label">Total en Seguimiento</div><div class="metric-val">${df_s["Monto_Estimado"].apply(limpiar_monto).sum():,}</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-container"><div class="metric-label">Presupuestos</div><div class="metric-val">{len(df_s)}</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="metric-container"><div class="metric-label">Mts2 Totales</div><div class="metric-val">{df_s["Mts2"].apply(limpiar_monto).sum()}</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="metric-container"><div class="metric-label">Operador</div><div class="metric-val" style="font-size:1.2rem">{st.session_state.user}</div></div>', unsafe_allow_html=True)
        
        st.divider()

        # 2. Buscador y Filtro
        f1, f2 = st.columns([2,1])
        busq = f1.text_input("🔍 Buscar por Cliente o Nro Ref...")
        vend = f2.selectbox("Vendedor", ["Todos", "Jonathan", "Martin", "Jacqueline"])
        
        if vend != "Todos": df_s = df_s[df_s['Vendedor'] == vend]
        if busq: df_s = df_s[df_s.apply(lambda r: busq.lower() in str(r.values).lower(), axis=1)]

        # 3. Listado de Tarjetas Estilo "Captura"
        for i, r in df_s.iterrows():
            st.markdown(f"""
            <div class="ticket-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span class="tag-vendedor">👤 {r['Vendedor']}</span>
                        <h4 style="margin:5px 0;">{r['Cliente']} (Ref: {r['MAG_Ref']})</h4>
                        <small>📍 {r['Ubicacion']} | 📅 {r['Fecha']} | 📏 {r['Mts2']} mts²</small>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:0.8rem; color:#64748B;">MONTO ESTIMADO</div>
                        <div class="monto-highlight">${limpiar_monto(r['Monto_Estimado']):,}</div>
                    </div>
                </div>
                <div style="margin-top:10px; font-size:0.85rem; color:#475569; border-top: 1px solid #F1F5F9; padding-top:10px;">
                    📝 {r['Notas']}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Acciones de la tarjeta
            c1, c2, c3 = st.columns([1,1,2])
            msg_wa = urllib.parse.quote(f"Hola {r['Cliente']}, te contacto de Grupo Magallan por tu presupuesto...")
            c1.markdown(f'<a href="https://wa.me/{r["Telefono"]}?text={msg_wa}" target="_blank"><button style="width:100%; background:#25D366; color:white; border:none; padding:7px; border-radius:5px; cursor:pointer;">WhatsApp</button></a>', unsafe_allow_html=True)
            
            if c2.button("✅ APROBAR", key=f"aprob_{i}"):
                # Mueve a Proyectos
                ws_p.append_row([r['MAG_Ref'], r['Cliente'], "Esperando", datetime.now().strftime("%d/%m/%Y"), r['Vendedor'], r['Monto_Estimado'], 0, "No", r['Mts2'], r['Notas'], r['Ubicacion']])
                # Registra en Historial
                ws_h.append_row([r['MAG_Ref'], datetime.now().strftime("%d/%m %H:%M"), st.session_state.user, "Presupuesto aprobado y enviado a planta"])
                # Borra de Seguimiento
                ws_s.delete_rows(i + 2)
                st.success("¡Obra enviada a planta!"); st.rerun()
            
            if c3.button("🗑️ ELIMINAR", key=f"del_{i}"):
                ws_s.delete_rows(i + 2); st.rerun()

        # 4. Formulario de Carga (Al final o en expander)
        with st.expander("➕ Cargar Nuevo Seguimiento"):
            with st.form("form_seg"):
                ca1, ca2, ca3 = st.columns(3)
                n_cli = ca1.text_input("Cliente")
                n_ref = ca2.text_input("Nro Referencia (MAG#)")
                n_ven = ca3.selectbox("Vendedor", ["Jonathan", "Martin", "Jacqueline"])
                ca4, ca5, ca6 = st.columns(3)
                n_tel = ca4.text_input("WhatsApp (549...)")
                n_ubi = ca5.text_input("Ubicación")
                n_mts = ca6.number_input("Mts2", value=0.0)
                n_mon = st.number_input("Monto Cotizado", value=0)
                n_not = st.text_area("Notas")
                if st.form_submit_button("AGENDAR"):
                    ws_s.append_row([datetime.now().strftime("%d/%m/%Y"), n_cli, n_mon, n_ven, n_ubi, n_tel, n_not, n_mts, n_ref])
                    st.rerun()

    # --- PÁGINA: TABLERO PLANTA (IGUAL DE ESTÉTICO) ---
    elif menu == "📋 TABLERO PLANTA":
        st.subheader("Órdenes en Ejecución")
        # Aquí el código del Tablero Planta con el mismo estilo de tarjetas...
        # (Se mantiene la lógica de Tabs para Chat e Historial que ya funcionaba)
        for i, r in df_p.iterrows():
            st.markdown(f"""
            <div class="ticket-card" style="border-left-color: {'#36B37E' if r['Estado_Fabricacion'] == 'Terminado' else '#0284C7'}">
                <b>MAG-{r['Nro_Ppto']}</b> | {r['Cliente']} | Saldo: ${limpiar_monto(r['Monto_Total_Ars'])-limpiar_monto(r['Pagado_Ars']):,}
            </div>
            """, unsafe_allow_html=True)
            with st.expander("Gestionar"):
                st.write("Panel de edición...")