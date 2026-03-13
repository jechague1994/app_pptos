import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Magallan - Gestión de Saldos", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8FAFC; color: #1E293B; }
    .panel-saldos {
        background: white; border: 1px solid #E2E8F0; border-left: 6px solid #0284C7;
        border-radius: 8px; padding: 15px; margin-bottom: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .monto-deuda { color: #E11D48; font-size: 1.4rem; font-weight: bold; }
    .monto-ok { color: #10B981; font-size: 1.4rem; font-weight: bold; }
    .vendedor-tag { 
        background-color: #F1F5F9; color: #475569; 
        padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;
    }
    [data-testid="stMetricValue"] { color: #0284C7; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource(ttl=600)
def conectar_gs():
    try:
        return gspread.authorize(Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        ))
    except Exception as e:
        st.error("Error de conexión con Google Sheets.")
        return None

def obtener_datos():
    gc = conectar_gs()
    if gc:
        try:
            sh = gc.open("Gestion_Magallan")
            try:
                ws = sh.worksheet("Saldos_Simples")
            except:
                ws = sh.add_worksheet(title="Saldos_Simples", rows="1000", cols="5")
                ws.append_row(["Nro_Ppto", "Cliente", "Monto_Total", "Anticipo", "Vendedor"])
            
            df = pd.DataFrame(ws.get_all_records())
            # Asegurar que la columna Vendedor existe en el DF aunque el Excel sea viejo
            if 'Vendedor' not in df.columns:
                df['Vendedor'] = "Sin asignar"
            return df, ws
        except Exception as e:
            st.error(f"Error al obtener datos: {e}")
    return pd.DataFrame(), None

# --- 3. INTERFAZ ---
st.title("📊 Control de Saldos Magallan")

df, ws = obtener_datos()

# MÉTRICAS GENERALES
if not df.empty:
    df['Monto_Total'] = pd.to_numeric(df['Monto_Total'], errors='coerce').fillna(0)
    df['Anticipo'] = pd.to_numeric(df['Anticipo'], errors='coerce').fillna(0)
    df['Saldo'] = df['Monto_Total'] - df['Anticipo']
    
    c1, c2, c3 = st.columns(3)
    c1.metric("TOTAL PRESUPUESTADO", f"${df['Monto_Total'].sum():,.0f}")
    c2.metric("COBRADO TOTAL", f"${df['Anticipo'].sum():,.0f}")
    c3.metric("SALDO PENDIENTE", f"${df['Saldo'].sum():,.0f}")
    st.divider()

col_izq, col_der = st.columns([1, 2.2])

with col_izq:
    st.subheader("➕ Cargar Ppto")
    with st.form("nuevo_ppto", clear_on_submit=True):
        n = st.text_input("Nro MAG#")
        cl = st.text_input("Cliente")
        # Vendedores actualizados
        vendedor = st.selectbox("Seleccionar Vendedor", ["Jonathan", "Jacqueline", "Roberto"])
        mt = st.number_input("Monto Total ($)", min_value=0.0)
        an = st.number_input("Anticipo ($)", min_value=0.0)
        
        if st.form_submit_button("REGISTRAR", use_container_width=True):
            if n and cl:
                ws.append_row([n, cl, mt, an, vendedor])
                st.success("¡Registrado con éxito!")
                st.rerun()

with col_der:
    st.subheader("📋 Listado de Saldos")
    if not df.empty:
        busc = st.text_input("🔍 Buscar por Cliente, MAG# o Vendedor...")
        # Buscador que revisa en todas las columnas
        df_ver = df[df.apply(lambda r: busc.lower() in str(r.values).lower(), axis=1)] if busc else df
        
        for i, r in df_ver.iterrows():
            saldo_r = r['Saldo']
            color_borde = '#E11D48' if saldo_r > 0 else '#10B981'
            
            st.markdown(f"""
            <div class="panel-saldos" style="border-left-color: {color_borde};">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <b>MAG-{r['Nro_Ppto']} | {r['Cliente']}</b> 
                        <span class="vendedor-tag">👤 {r['Vendedor']}</span><br>
                        <small>Total: ${r['Monto_Total']:,.0f} | Cobrado: ${r['Anticipo']:,.0f}</small>
                    </div>
                    <div style="text-align:right;">
                        <span class="{'monto-deuda' if saldo_r > 0 else 'monto-ok'}">
                            {f'Debe: ${saldo_r:,.0f}' if saldo_r > 0 else 'Saldado'}
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander(f"✏️ Editar Montos de MAG-{r['Nro_Ppto']}"):
                ec1, ec2, ec3 = st.columns([1.5, 1.5, 1])
                nuevo_t = ec1.number_input("Modificar Total ($)", value=float(r['Monto_Total']), key=f"t{i}")
                nuevo_a = ec2.number_input("Actualizar Anticipo ($)", value=float(r['Anticipo']), key=f"a{i}")
                
                # Recordatorio de vendedor (no editable)
                st.caption(f"Vendedor asignado: {r['Vendedor']}")
                
                if ec3.button("Guardar", key=f"b{i}", use_container_width=True):
                    # Actualizar celdas en C (3) y D (4)
                    ws.update_cell(i + 2, 3, nuevo_t)
                    ws.update_cell(i + 2, 4, nuevo_a)
                    st.rerun()
            st.write("")
    else:
        st.info("Todavía no hay presupuestos cargados.")