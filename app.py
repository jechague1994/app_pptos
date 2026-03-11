import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 1. Configuración de página
st.set_page_config(page_title="Grupo Magallan | Gestión", layout="wide", page_icon="🏗️")

# 2. Conexión con Google Sheets
@st.cache_resource
def conectar_google():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        st.stop()

client = conectar_google()
SHEET_NAME = "Gestion_Magallan"

# 3. Funciones de Carga y Escritura
def cargar_datos():
    sh = client.open(SHEET_NAME)
    ws = sh.worksheet("Proyectos")
    df = pd.DataFrame(ws.get_all_records())
    return sh, ws, df

sh, ws_proyectos, df_proyectos = cargar_datos()

# --- INTERFAZ DE USUARIO ---
st.title("🏗️ Gestión de Presupuestos - Grupo Magallan")

# Menú lateral para navegar entre Crear o Editar
menu = st.sidebar.radio("Ir a:", ["📊 Ver y Editar Existentes", "🆕 Crear Nuevo Presupuesto"])

if menu == "🆕 Crear Nuevo Presupuesto":
    st.header("Cargar Nuevo Presupuesto")
    
    with st.form("form_nuevo_ppto", clear_on_submit=True):
        c1, c2 = st.columns(2)
        
        with c1:
            nro_ppto = st.number_input("Número de Presupuesto", min_value=1, step=1)
            cliente = st.text_input("Nombre del Cliente")
            tipo_pago = st.selectbox("Tipo de Pago", ["Anticipo", "Pago Total"])
            iva_opcion = st.radio("¿Incluye IVA?", ["Sin IVA", "Con IVA (21%)"], horizontal=True)

        with c2:
            monto_total = st.number_input("Valor Total del Presupuesto (ARS)", min_value=0.0, format="%.2f")
            
            if tipo_pago == "Anticipo":
                monto_abonado = st.number_input("Monto del Anticipo (ARS)", min_value=0.0, max_value=monto_total, format="%.2f")
            else:
                monto_abonado = monto_total
                st.info(f"Se registrará el pago total por $ {monto_total:,.2f}")
            
            saldo_restante = monto_total - monto_abonado
            st.warning(f"*Saldo Restante: $ {saldo_restante:,.2f}*")

        notas = st.text_area("Notas adicionales")
        boton_crear = st.form_submit_button("Registrar Presupuesto")

        if boton_crear:
            if nro_ppto and cliente:
                try:
                    # Preparar la fila para Google Sheets 
                    # El orden debe coincidir con tus columnas (A: Nro, B: Cliente, C: Estado, D: Total, E: Pagado, F: IVA, G: Notas...)
                    nueva_fila = [
                        nro_ppto, 
                        cliente, 
                        "Esperando", # Estado inicial por defecto
                        monto_total, 
                        monto_abonado, 
                        iva_opcion, 
                        notas
                    ]
                    ws_proyectos.append_row(nueva_fila)
                    st.success(f"✅ Presupuesto #{nro_ppto} de {cliente} creado con éxito.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
            else:
                st.error("Por favor completa el Número de Presupuesto y el nombre del Cliente.")

elif menu == "📊 Ver y Editar Existentes":
    if not df_proyectos.empty:
        # Buscador / Selector
        lista_ppto = df_proyectos["Nro_Ppto"].unique()
        ppto_sel = st.selectbox("Seleccione Presupuesto para editar:", lista_ppto)
        
        idx = df_proyectos[df_proyectos["Nro_Ppto"] == ppto_sel].index[0]
        datos = df_proyectos.iloc[idx]
        
        st.divider()
        
        with st.form("form_editar"):
            col1, col2 = st.columns(2)
            with col1:
                nuevo_estado = st.selectbox("Estado", ["Esperando", "Preparacion", "Terminado", "Entregado"], 
                                          index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(datos['Estado_Fabricacion']) if datos['Estado_Fabricacion'] in ["Esperando", "Preparacion", "Terminado", "Entregado"] else 0)
                nuevo_pagado = st.number_input("Actualizar Monto Pagado (ARS)", value=float(datos.get('Pagado_Ars', 0)))
            
            with col2:
                st.write(f"*Cliente:* {datos['Cliente']}")
                st.write(f"*Monto Total:* $ {datos['Monto_Total_Ars']:,.2f}")
                st.write(f"*IVA:* {datos.get('IVA', 'No especificado')}")
                saldo = float(datos['Monto_Total_Ars']) - nuevo_pagado
                st.subheader(f"Saldo: $ {saldo:,.2f}")

            if st.form_submit_button("Actualizar"):
                fila_excel = int(idx) + 2
                # Ejemplo de columnas: C (3) es Estado, E (5) es Pagado
                ws_proyectos.update_cell(fila_excel, 3, nuevo_estado)
                ws_proyectos.update_cell(fila_excel, 5, nuevo_pagado)
                st.success("¡Datos actualizados!")
                st.rerun()
    else:
        st.info("No hay presupuestos cargados.")