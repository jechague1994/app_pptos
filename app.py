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

# 3. Función para cargar datos frescos
def cargar_datos():
    sh = client.open(SHEET_NAME)
    ws = sh.worksheet("Proyectos")
    df = pd.DataFrame(ws.get_all_records())
    return sh, ws, df

sh, ws_proyectos, df_proyectos = cargar_datos()

st.title("🏗️ Gestión de Presupuestos - Grupo Magallan")

# Menú lateral
menu = st.sidebar.radio("Ir a:", ["📊 Ver y Editar Existentes", "🆕 Crear Nuevo Presupuesto"])

if menu == "🆕 Crear Nuevo Presupuesto":
    st.header("Cargar Nuevo Presupuesto")
    with st.form("form_nuevo", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nro = st.number_input("Nro Presupuesto", min_value=1, step=1)
            cli = st.text_input("Cliente")
            iva = st.selectbox("IVA", ["Sin IVA", "Con IVA (21%)"])
        with c2:
            total = st.number_input("Valor Total (ARS)", min_value=0.0)
            tipo_p = st.selectbox("Tipo de Pago", ["Anticipo", "Pago Total"])
            if tipo_p == "Anticipo":
                pago = st.number_input("Monto Abonado", min_value=0.0, max_value=total)
            else:
                pago = total
                st.info(f"Se registrará pago total: ${total:,.2f}")
        
        saldo = total - pago
        st.write(f"*Saldo Restante: ${saldo:,.2f}*")
        
        if st.form_submit_button("Registrar Nuevo"):
            # Ajustado al orden de tus columnas: Nro_Ppto, Cliente, Estado_Fabricacion, notas_planta, Monto_Total_Ar, Pagado_Ars
            nueva_fila = [nro, cli, "Esperando", "", total, pago, iva]
            ws_proyectos.append_row(nueva_fila)
            st.success("✅ Guardado correctamente")
            st.rerun()

elif menu == "📊 Ver y Editar Existentes":
    if not df_proyectos.empty:
        # Usamos los nombres exactos de tus columnas
        lista_ppto = df_proyectos["Nro_Ppto"].unique()
        sel = st.selectbox("Seleccione presupuesto:", lista_ppto)
        
        idx = df_proyectos[df_proyectos["Nro_Ppto"] == sel].index[0]
        datos = df_proyectos.iloc[idx]
        
        with st.form("form_edicion"):
            col1, col2 = st.columns(2)
            with col1:
                # Corregido: Monto_Total_Ar (sin la 's' al final según tu captura)
                m_total = float(datos.get("Monto_Total_Ar", 0))
                st.write(f"*Cliente:* {datos['Cliente']}")
                st.write(f"*Monto Total:* ${m_total:,.2f}")
                
                nuevo_estado = st.selectbox("Estado", ["Esperando", "Preparacion", "Terminado", "Entregado"],
                                          index=["Esperando", "Preparacion", "Terminado", "Entregado"].index(datos["Estado_Fabricacion"]) if datos["Estado_Fabricacion"] in ["Esperando", "Preparacion", "Terminado", "Entregado"] else 0)
            
            with col2:
                actual_pago = float(datos.get("Pagado_Ars", 0))
                nuevo_pago = st.number_input("Actualizar Pago Acumulado", value=actual_pago)
                st.metric("Saldo Pendiente", f"${m_total - nuevo_pago:,.2f}")

            if st.form_submit_button("Actualizar Datos"):
                fila = int(idx) + 2
                ws_proyectos.update_cell(fila, 3, nuevo_estado) # Col C: Estado
                ws_proyectos.update_cell(fila, 6, nuevo_pago)   # Col F: Pagado_Ars
                st.success("✅ ¡Actualizado!")
                st.rerun()