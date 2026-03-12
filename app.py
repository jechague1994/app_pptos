import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fpdf import FPDF
import urllib.parse
import plotly.express as px
import io

# --- 1. CONFIGURACIÓN VISUAL (ESTILO LEGIBLE Y LIMPIO) ---
st.set_page_config(page_title="Grupo Magallan - Sistema de Gestión", layout="wide")

st.markdown("""
    <style>
    /* Fondo general claro */
    .stApp { background-color: #F8F9FA; color: #212529; }
    
    /* Contenedores de Métricas */
    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #E9ECEF;
        text-align: center;
    }
    .metric-val { color: #0056b3; font-size: 1.8rem; font-weight: 700; }
    .metric-label { color: #6C757D; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; }

    /* Tarjetas de Obra */
    .obra-card {
        background: white;
        border-left: 5px solid #0056b3;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .obra-card:hover { border-color: #00D2FF; }
    
    /* Botones y UI */
    .stButton>button { border-radius: 5px; font-weight: 500; }
    .tag-vendedor { background: #E9ECEF; color: #495057; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCIONES DE SEGURIDAD (ANTI-ERRORES) ---
def limpiar_monto(valor):
    """Evita ValueErrors al convertir moneda."""
    if pd.isna(valor) or valor == "": return 0
    try:
        if isinstance(valor, str):
            # Elimina $, puntos de miles y cambia coma decimal por punto
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

def traer_datos(nombre_hoja, columnas_esperadas):
    """Evita KeyErrors asegurando que las columnas existan."""
    try:
        gc = conectar_gs()
        sh = gc.open("Gestion_Magallan")
        ws = sh.worksheet(nombre_hoja)
        df = pd.DataFrame(ws.get_all_records())
        
        # Si la hoja está vacía o faltan columnas, creamos un DF compatible
        for col in columnas_esperadas:
            if col not in df.columns:
                df[col] = ""
        return df, ws
    except Exception as e:
        st.warning(f"Aviso en {nombre_hoja}: {e}")
        return pd.DataFrame(columns=columnas_esperadas), None

# --- 3. GENERADOR DE PDF (CORREGIDO) ---
def crear_pdf_ppto(tk):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    # Título
    pdf.cell(190, 10, f"ORDEN DE TRABAJO: MAG-{tk.get('Nro_Ppto', 'S/N')}", 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    
    # Datos en tabla simple para evitar fallos de encoding
    campos = [
        ["CLIENTE:", str(tk.get('Cliente', ''))],
        ["VENDEDOR:", str(tk.get('Vendedor', ''))],
        ["UBICACION:", str(tk.get('Ubicacion', ''))],
        ["SUPERFICIE:", f"{tk.get('Mts2', '0')} mts2"],
        ["SALDO PENDIENTE:", f"${limpiar_monto(tk.get('Monto_Total_Ars',0)) - limpiar_monto(tk.get('Pagado_Ars',0))}"]
    ]
    
    for label, valor in campos:
        pdf.set_font("Arial", 'B', 10); pdf.cell(50, 8, label, 0)
        pdf.set_font("Arial", size=10); pdf.cell(140, 8, valor, 0, 1)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10); pdf.cell(0, 8, "NOTAS Y MATERIALES:", "B", 1)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 7, str(tk.get('Materiales_Pendientes', 'Sin detalles.')))
    
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 4. LÓGICA DE ACCESO ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.title("Magallan Enterprise")
        user = st.selectbox("Operador", ["---", "Jonathan", "Martin", "Jacqueline"])
        pw = st.text_input("Clave", type="password")
        if st.button("INGRESAR", use_container_width=True):
            if user != "---" and str(st.secrets["usuarios"].get(user)) == pw:
                st.session_state.auth = True
                st.session_state.user = user
                st.rerun()
else:
    # --- 5. CARGA DE DATOS SEGUROS ---
    columnas_ppto = ['Nro_Ppto', 'Cliente', 'Estado_Fabricacion', 'Fecha_Ingreso', 'Vendedor', 'Monto_Total_Ars', 'Pagado_Ars', 'Iva', 'Mts2', 'Materiales_Pendientes', 'Ubicacion']
    df_p, ws_p = traer_datos("Proyectos", columnas_ppto)
    
    st.sidebar.title(f"👤 {st.session_state.user}")
    menu = st.sidebar.radio("Navegación", ["📊 Dashboard", "🏗️ Tablero de Planta", "📅 Seguimiento", "➕ Nueva Carga"])
    
    # --- DASHBOARD ---
    if menu == "📊 Dashboard":
        st.subheader("Estado de Cuenta y Operaciones")
        if not df_p.empty:
            # Cálculos robustos
            total_vta = df_p['Monto_Total_Ars'].apply(limpiar_monto).sum()
            total_cobrado = df_p['Pagado_Ars'].apply(limpiar_monto).sum()
            saldo = total_vta - total_cobrado
            
            m1, m2, m3 = st.columns(3)
            m1.markdown(f'<div class="metric-card"><div class="metric-label">Saldo a Cobrar</div><div class="metric-val">${saldo:,}</div></div>', unsafe_allow_html=True)
            m2.markdown(f'<div class="metric-card"><div class="metric-label">En Producción</div><div class="metric-val">{len(df_p[df_p["Estado_Fabricacion"] != "Entregado"])}</div></div>', unsafe_allow_html=True)
            m3.markdown(f'<div class="metric-card"><div class="metric-label">Total Cobrado</div><div class="metric-val" style="color:#28a745;">${total_cobrado:,}</div></div>', unsafe_allow_html=True)
            
            st.write("### Producción por Vendedor")
            fig = px.bar(df_p, x='Vendedor', color='Estado_Fabricacion', barmode='group', template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

    # --- TABLERO DE PLANTA ---
    elif menu == "🏗️ Tablero de Planta":
        st.subheader("Control de Órdenes en Planta")
        busqueda = st.text_input("🔍 Buscar por Cliente o Nro MAG...")
        
        # Filtro de búsqueda
        df_filtrado = df_p
        if busqueda:
            df_filtrado = df_p[df_p.apply(lambda r: busqueda.lower() in str(r.values).lower(), axis=1)]

        for i, r in df_filtrado.iterrows():
            # Clave única para botones basada en Nro_Ppto e índice para evitar DuplicateKeyError
            key_id = f"{r['Nro_Ppto']}_{i}"
            
            saldo_obra = limpiar_monto(r['Monto_Total_Ars']) - limpiar_monto(r['Pagado_Ars'])
            
            with st.container():
                st.markdown(f"""
                <div class="obra-card">
                    <div style="display:flex; justify-content:space-between;">
                        <b>MAG-{r['Nro_Ppto']} | {r['Cliente']}</b>
                        <span class="tag-vendedor">{r['Vendedor']}</span>
                    </div>
                    <div style="font-size: 0.9rem; margin-top:5px;">
                        📍 {r['Ubicacion']} | 📏 {r['Mts2']} mts² | 💰 Saldo: <b>${saldo_obra:,}</b>
                    </div>
                    <div style="color: #6C757D; font-size: 0.8rem;">Estado: {r['Estado_Fabricacion']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns([1, 4])
                if col1.button("📝 Gestionar", key=f"btn_edit_{key_id}"):
                    st.session_state.selected_mag = r['Nro_Ppto']
                
                # Panel de gestión rápida si está seleccionado
                if st.session_state.get('selected_mag') == r['Nro_Ppto']:
                    with st.expander(f"Configuración de MAG-{r['Nro_Ppto']}", expanded=True):
                        idx_excel = i + 2
                        new_pagado = st.number_input("Monto Pagado", value=limpiar_monto(r['Pagado_Ars']), key=f"pay_{key_id}")
                        new_estado = st.selectbox("Estado", ["Esperando", "Preparacion", "Terminado", "Entregado"], 
                                                 index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(r['Estado_Fabricacion']) if r['Estado_Fabricacion'] in ["Esperando", "Preparacion", "Terminado", "Entregado"] else 0,
                                                 key=f"est_{key_id}")
                        
                        if st.button("Actualizar Obra", key=f"save_{key_id}"):
                            ws_p.update_cell(idx_excel, 7, new_pagado) # Columna Pagado_Ars
                            ws_p.update_cell(idx_excel, 3, new_estado) # Columna Estado_Fabricacion
                            st.success("¡Datos guardados!")
                            st.rerun()
                        
                        pdf_data = crear_pdf_ppto(r)
                        st.download_button("📥 Descargar Orden PDF", pdf_data, f"MAG_{r['Nro_Ppto']}.pdf", key=f"pdf_{key_id}")

    # --- NUEVA CARGA ---
    elif menu == "➕ Nueva Carga":
        st.subheader("Registrar Nueva Orden de Trabajo")
        with st.form("form_carga"):
            c1, c2, c3 = st.columns(3)
            f_nro = c1.text_input("MAG#")
            f_cli = c2.text_input("Cliente")
            f_ven = c3.selectbox("Vendedor", ["Jonathan", "Martin", "Jacqueline"])
            
            c4, c5, c6 = st.columns(3)
            f_ubi = c4.text_input("Ubicación")
            f_mts = c5.number_input("Superficie (mts2)", min_value=0.0)
            f_tot = c6.number_input("Monto Total ($)", min_value=0)
            
            f_det = st.text_area("Notas y Materiales Pendientes")
            
            if st.form_submit_button("REGISTRAR E INGRESAR A PLANTA"):
                ws_p.append_row([f_nro, f_cli, "Esperando", datetime.now().strftime("%d/%m/%Y"), f_ven, f_tot, 0, "sin iva", f_mts, f_det, f_ubi])
                st.balloons()
                st.success("Orden creada correctamente.")

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()