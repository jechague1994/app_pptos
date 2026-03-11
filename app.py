import streamlit as st
import pandas as pd

# 1. Configuración de la página
st.set_page_config(page_title="Grupo Magallan | Gestión", layout="wide", page_icon="🏗️")

st.title("🏗️ Panel de Gestión Operativa - Grupo Magallan")

# ID de tu Spreadsheet (confirmado en tus capturas)
SHEET_ID = "1Bf2R7v_f-2_uV2M7uXq7y65oE9e_qV2M7uXq7y65oE9"

@st.cache_data(ttl=30)
def cargar_csv(sheet_name):
    # Formato de URL para exportar pestañas específicas como CSV
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        # Normalizar nombres de columnas a minúsculas y sin espacios
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except Exception as e:
        return None

# Intentamos cargar con los nombres exactos de tus fotos
df_proyectos = cargar_csv("Proyectos")
df_logistica = cargar_csv("Logistica")
df_chat = cargar_csv("Chat_Interno")

# Verificación de carga
if df_proyectos is not None and not df_proyectos.empty:
    st.sidebar.success("✅ Conexión Exitosa")
    
    # Selector de presupuesto
    col_id = "nro_ppto"
    if col_id in df_proyectos.columns:
        lista_ppto = df_proyectos[col_id].unique()
        ppto_sel = st.sidebar.selectbox("Seleccione Nro de Presupuesto:", lista_ppto)
        
        # Filtrado de datos
        datos_p = df_proyectos[df_proyectos[col_id] == ppto_sel].iloc[0]
        
        # --- INTERFAZ ---
        tab1, tab2, tab3 = st.tabs(["📊 Fabricación", "🚚 Logística", "💬 Chat"])

        with tab1:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Datos del Cliente")
                st.write(f"*Cliente:* {datos_p.get('cliente', 'N/A')}")
                st.write(f"*Estado:* {datos_p.get('estado_fabricacion', 'N/A')}")
            with c2:
                st.subheader("Saldos")
                total = float(datos_p.get('monto_total_ars', 0))
                pagado = float(datos_p.get('pagado_ars', 0))
                st.metric("Saldo Pendiente", f"$ {total - pagado:,.2f}")

        with tab2:
            if df_logistica is not None and ppto_sel in df_logistica[col_id].values:
                datos_l = df_logistica[df_logistica[col_id] == ppto_sel].iloc[0]
                st.write(f"*Técnicos:* {datos_l.get('tecnicos', 'Pendiente')}")
                st.write(f"*Fecha:* {datos_l.get('fecha_instalacion', 'Sin fecha')}")
                st.info(f"*Estado Entrega:* {datos_l.get('estado_entrega', '-')}")
            else:
                st.warning("No se encontraron datos en la pestaña 'Logistica'.")

        with tab3:
            if df_chat is not None:
                mensajes = df_chat[df_chat[col_id].astype(str) == str(ppto_sel)]
                if not mensajes.empty:
                    for _, m in mensajes.iterrows():
                        with st.chat_message("user"):
                            st.write(f"*{m.get('usuario', 'Admin')}*: {m.get('mensaje', '')}")
                else:
                    st.write("Sin mensajes para este presupuesto.")
    else:
        st.error(f"No se encontró la columna '{col_id}' en la pestaña Proyectos.")
else:
    st.error("No se pudo leer la pestaña 'Proyectos'.")
    st.info("Asegúrate de haber ido a Archivo > Compartir > Publicar en la Web en tu Google Sheets.")