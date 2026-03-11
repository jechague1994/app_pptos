import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 1. Configuración
st.set_page_config(page_title="Grupo Magallan | Gestión", layout="wide", page_icon="🏗️")
st.title("🏗️ Panel de Gestión Operativa - Grupo Magallan")

# 2. Conexión (Scopes de Sheets y Drive)
@st.cache_resource
def conectar_google():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"❌ Error de credenciales: {e}")
        st.stop()

client = conectar_google()
SHEET_NAME = "Gestion_Magallan"

# 3. Función para cargar y guardar
def cargar_datos():
    sh = client.open(SHEET_NAME)
    # Traemos las pestañas como DataFrames
    df_p = pd.DataFrame(sh.worksheet("Proyectos").get_all_records())
    df_l = pd.DataFrame(sh.worksheet("Logistica").get_all_records())
    return sh, df_p, df_l

sh, df_proyectos, df_logistica = cargar_datos()

# 4. Interfaz de Usuario
if not df_proyectos.empty:
    st.sidebar.success("✅ Conectado")
    
    # Selector de Presupuesto
    col_id = "Nro_Ppto" 
    lista_ppto = df_proyectos[col_id].unique()
    ppto_sel = st.sidebar.selectbox("Seleccione Nro de Presupuesto:", lista_ppto)
    
    # Obtener fila actual para edición
    idx_fila = df_proyectos[df_proyectos[col_id] == ppto_sel].index[0]
    datos_p = df_proyectos.iloc[idx_fila]

    # --- PESTAÑAS ---
    tab_ver, tab_editar = st.tabs(["📊 Visualizar", "✏️ Editar Información"])

    with tab_ver:
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Estado de Fabricación", datos_p.get('Estado_Fabricacion', 'N/A'))
            st.write(f"*Cliente:* {datos_p.get('Cliente', 'N/A')}")
        with c2:
            total = float(datos_p.get('Monto_Total_Ars', 0))
            pagado = float(datos_p.get('Pagado_Ars', 0))
            st.metric("Saldo Pendiente", f"$ {total - pagado:,.2f}")

    with tab_editar:
        st.subheader(f"Modificar Presupuesto #{ppto_sel}")
        
        with st.form("form_edicion"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Campo para Estado (con las opciones que usas en tu Excel)
                nuevo_estado = st.selectbox(
                    "Estado de Fabricación", 
                    ["Esperando", "Preparacion", "Terminado", "Entregado"],
                    index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(datos_p['Estado_Fabricacion']) if datos_p['Estado_Fabricacion'] in ["Esperando", "Preparacion", "Terminado", "Entregado"] else 0
                )
                nueva_nota = st.text_area("Notas de Planta", value=datos_p.get('notas_planta', ''))
            
            with col2:
                # Campos para Precios
                nuevo_monto = st.number_input("Monto Total (ARS)", value=float(datos_p.get('Monto_Total_Ars', 0)))
                nuevo_pagado = st.number_input("Monto Pagado (ARS)", value=float(datos_p.get('Pagado_Ars', 0)))
            
            boton_guardar = st.form_submit_button("Guardar Cambios")

            if boton_guardar:
                try:
                    ws_proyectos = sh.worksheet("Proyectos")
                    # En Google Sheets las filas empiezan en 1 y la fila 1 es el encabezado, por eso idx+2
                    fila_real = int(idx_fila) + 2
                    
                    # Actualizamos las celdas específicas (ajusta la letra de columna según tu Excel)
                    # Ejemplo: C es Estado, D es Notas, E es Monto, F es Pagado
                    ws_proyectos.update_cell(fila_real, 3, nuevo_estado)       # Columna C: Estado_Fabricacion
                    ws_proyectos.update_cell(fila_real, 4, nueva_nota)         # Columna D: notas_planta
                    ws_proyectos.update_cell(fila_real, 5, nuevo_monto)        # Columna E: Monto_Total_Ars
                    ws_proyectos.update_cell(fila_real, 6, nuevo_pagado)       # Columna F: Pagado_Ars
                    
                    st.success("✅ ¡Datos actualizados en Google Sheets!")
                    st.rerun() # Recarga la app para ver los cambios
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

else:
    st.warning("No se encontraron datos.")