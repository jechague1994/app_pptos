import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 1. Configuración de la página
st.set_page_config(page_title="Grupo Magallan | Gestión", layout="wide", page_icon="🏗️")

st.title("🏗️ Panel de Gestión Operativa - Grupo Magallan")

# 2. Conexión con Google Sheets usando Secrets y Scopes ampliados
@st.cache_resource
def conectar_google():
    try:
        # Definimos los permisos necesarios (Sheets + Drive) para evitar el error 403
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Cargamos las credenciales desde los Secrets de Streamlit
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"❌ Error de configuración de credenciales: {e}")
        st.stop()

client = conectar_google()

# Nombre exacto de tu archivo en Google Drive
SHEET_NAME = "Gestion_Magallan"

@st.cache_data(ttl=60) # Los datos se refrescan cada minuto
def cargar_datos():
    try:
        sh = client.open(SHEET_NAME)
        
        # Cargamos las 3 pestañas confirmadas en tus capturas
        df_p = pd.DataFrame(sh.worksheet("Proyectos").get_all_records())
        df_l = pd.DataFrame(sh.worksheet("Logistica").get_all_records())
        df_c = pd.DataFrame(sh.worksheet("Chat_Interno").get_all_records())
        
        # Normalizamos nombres de columnas para evitar errores de tipeo
        for df in [df_p, df_l, df_c]:
            df.columns = [str(c).strip().lower() for c in df.columns]
            
        return df_p, df_l, df_c
    except Exception as e:
        st.error(f"❌ Error al leer el Excel: {e}")
        return None, None, None

# 3. Ejecución de la carga
df_proyectos, df_logistica, df_chat = cargar_datos()

if df_proyectos is not None and not df_proyectos.empty:
    # Sidebar: Selección de Obra
    st.sidebar.success("✅ Conexión Establecida")
    
    col_id = "nro_ppto" # Nombre de la columna en tu Excel
    if col_id in df_proyectos.columns:
        lista_ppto = df_proyectos[col_id].unique()
        ppto_sel = st.sidebar.selectbox("Seleccione Nro de Presupuesto:", lista_ppto)
        
        # Filtrado de datos por presupuesto seleccionado
        datos_p = df_proyectos[df_proyectos[col_id] == ppto_sel].iloc[0]
        
        # --- DISEÑO DE PESTAÑAS ---
        tab1, tab2, tab3 = st.tabs(["📊 Fabricación", "🚚 Logística", "💬 Chat"])

        with tab1:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Información General")
                st.write(f"*Cliente:* {datos_p.get('cliente', 'N/A')}")
                st.info(f"*Estado Fabricación:* {datos_p.get('estado_fabricacion', 'Pendiente')}")
            with c2:
                st.subheader("Finanzas")
                # Cálculo de saldo (Monto Total - Pagado)
                total = float(datos_p.get('monto_total_ars', 0))
                pagado = float(datos_p.get('pagado_ars', 0))
                st.metric("Saldo Pendiente", f"$ {total - pagado:,.2f}", delta_color="inverse")

        with tab2:
            if col_id in df_logistica.columns and ppto_sel in df_logistica[col_id].values:
                datos_l = df_logistica[df_logistica[col_id] == ppto_sel].iloc[0]
                st.write(f"*Técnicos Asignados:* {datos_l.get('tecnicos', 'No asignado')}")
                st.write(f"*Fecha Programada:* {datos_l.get('fecha_instalacion', 'Sin fecha')}")
                st.warning(f"*Estado de Entrega:* {datos_l.get('estado_entrega', '-')}")
            else:
                st.info("No hay datos logísticos registrados para este presupuesto.")

        with tab3:
            # Filtramos el chat por el número de presupuesto
            mensajes = df_chat[df_chat[col_id].astype(str) == str(ppto_sel)]
            if not mensajes.empty:
                for _, m in mensajes.iterrows():
                    with st.chat_message("user"):
                        st.write(f"*{m.get('usuario', 'Sistema')}*: {m.get('mensaje', '')}")
            else:
                st.write("No hay mensajes previos en esta obra.")
    else:
        st.error(f"No se encontró la columna '{col_id}' en el archivo.")
else:
    st.warning("Esperando conexión con Google Sheets...")