import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Gestor Pro v25", layout="wide")

st.title("🚀 Control de Ventas (v25 - Auto-Pago Corregido)")

conn = st.connection("gsheets", type=GSheetsConnection)

def lectura_segura():
    for i in range(3):
        try: return conn.read(ttl=0)
        except Exception: time.sleep(1)
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def obtener_tc():
    try: return round(requests.get("https://open.er-api.com/v6/latest/USD").json()["rates"]["MXN"], 2)
    except: return 18.50
tc_actual = obtener_tc()

# --- DATOS ACTUALES ---
df_nube = lectura_segura()
proximo_id = len(df_nube)

# --- RANGO SEMANAL ACTUAL ---
hoy = datetime.now()
inicio_semana = hoy - timedelta(days=hoy.weekday())
fin_semana = inicio_semana + timedelta(days=6)
rango_actual = f"{inicio_semana.strftime('%d/%m/%y')} al {fin_semana.strftime('%d/%m/%y')}"

# --- SIDEBAR: REGISTRO ---
with st.sidebar:
    st.header(f"📝 Registro (ID: {proximo_id})")
    nombre = st.text_input("PRODUCTO", placeholder="Nombre del producto")
    
    opciones_tienda = ["Hollister", "American Eagle", "Macys", "Finishline", "Guess", "Nike", "Aeropostale", "JDSports", "CUSTOM"]
    tienda_sel = st.selectbox("TIENDA", opciones_tienda)
    tienda_final = st.text_input("Tienda custom:") if tienda_sel == "CUSTOM" else tienda_sel
    
    usd_bruto_txt = st.text_input("COSTO USD", placeholder="Ej: 50.00")
    tc_mercado_txt = st.text_input("TIPO DE CAMBIO", value=str(tc_actual))
    venta_mxn_txt = st.text_input("VENTA FINAL (MXN)", placeholder="Ej: 1500.00")
    
    def limpiar_num(t):
        if not t: return 0.0
        try: return float(t.replace(',', '').replace('$', ''))
        except: return 0.0

    usd_bruto = limpiar_num(usd_bruto_txt)
    tc_mercado = limpiar_num(tc_mercado_txt)
    venta_mxn = limpiar_num(venta_mxn_txt)

    usd_tax = usd_bruto * 1.0825
    comi_mxn = (usd_tax * 0.12) * 19.5
    costo_tot_mxn = (usd_tax * tc_mercado) + comi_mxn
    ganancia_mxn = venta_mxn - costo_tot_mxn
    usd_final_eq = costo_tot_mxn / tc_mercado if tc_mercado > 0 else 0

    if st.button("CALCULAR 🔍", use_container_width=True):
        st.info(f"Comisión: ${comi_mxn:,.2f}\n\nInversión: ${costo_tot_mxn:,.2f}\n\nGanancia: ${ganancia_mxn:,.2f}")

    btn_guardar = st.button("GUARDAR EN NUBE ✅", use_container_width=True, type="primary")

    st.divider()
    st.header("🗑️ Borrar Registro")
    if not df_nube.empty:
        opciones_del = [f"{i} - {df_nube.loc[i, 'PRODUCTO']}" for i in reversed(df_nube.index)]
        seleccion = st.selectbox("ID a borrar:", opciones_del)
        if st.button("ELIMINAR SELECCIONADO", use_container_width=True):
            st.session_state.confirm_delete = True
        
        if st.session_state.get('confirm_delete', False):
            st.error("¿Confirmas?")
            c1, c2 = st.columns(2)
            if c1.button("SÍ", type="primary"):
                conn.update(data=df_nube.drop(int(seleccion.split(" - ")[0])))
                st.session_state.confirm_delete = False
                st.cache_data.clear()
                st.rerun()
            if c2.button("NO"):
                st.session_state.confirm_delete = False
                st.rerun()

# --- ACCIÓN GUARDAR ---
if btn_guardar and nombre and usd_bruto > 0:
    nuevo = pd.DataFrame([{
        "FECHA_REGISTRO": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "PRODUCTO": nombre, "TIENDA": tienda_final, "USD_BRUTO": usd_bruto,
        "USD_CON_8.25": usd_tax, "USD_FINAL_EQ": usd_final_eq, "TC_MERCADO": tc_mercado,
        "COMISION_PAGADA_MXN": comi_mxn, "COSTO_TOTAL_MXN": costo_tot_mxn,
        "VENTA_MXN": venta_mxn, "GANANCIA_MXN": ganancia_mxn, "RANGO_SEMANA": rango_actual,
        "ESTADO_PAGO": "🔴 Debe", "MONTO_RECIBIDO": 0.0, "FECHA": datetime.now().strftime("%d/%m/%Y")
    }])
    columnas = ["FECHA_REGISTRO", "PRODUCTO", "TIENDA", "USD_BRUTO", "USD_CON_8.25", "USD_FINAL_EQ", "TC_MERCADO", "COMISION_PAGADA_MXN", "COSTO_TOTAL_MXN", "VENTA_MXN", "GANANCIA_MXN", "RANGO_SEMANA", "ESTADO_PAGO", "MONTO_RECIBIDO", "FECHA"]
    conn.update(data=pd.concat([df_nube, nuevo[columnas]], ignore_index=True))
    st.cache_data.clear()
    st.rerun()

# --- HISTORIAL Y COBRANZA (CORRECCIÓN AUTO-PAGO) ---
st.subheader("📋 Historial y Cobranza")
if not df_nube.empty:
    # Mostramos la tabla. Nota: El ID (índice) es visible.
    df_para_editar = df_nube.sort_index(ascending=False)
    
    edited_df = st.data_editor(
        df_para_editar,
        column_config={
            "ESTADO_PAGO": st.column_config.SelectboxColumn("ESTADO", options=["🔴 Debe", "🟡 Abonado", "🟢 Pagado"]),
            "MONTO_RECIBIDO": st.column_config.NumberColumn("RECIBIDO", format="$%.2f")
        },
        disabled=[c for c in df_nube.columns if c not in ["ESTADO_PAGO", "MONTO_RECIBIDO"]],
        use_container_width=True, key="ed_v25"
    )

    if st.button("💾 GUARDAR CAMBIOS DE TABLA"):
        # Lógica de Auto-Pago: Antes de subir, revisamos fila por fila
        # Si alguien puso 'Pagado', igualamos el monto recibido a la venta
        for idx in edited_df.index:
            if edited_df.at[idx, "ESTADO_PAGO"] == "🟢 Pagado":
                edited_df.at[idx, "MONTO_RECIBIDO"] = edited_df.at[idx, "VENTA_MXN"]
        
        # Guardar en orden original de ID (sort_index)
        conn.update(data=edited_df.sort_index())
        st.success("¡Información actualizada!")
        st.cache_data.clear()
        st.rerun()

# --- REPORTES ---
st.divider()
st.subheader("💰 Reporte Semanal")
if not df_nube.empty:
    semanas = df_nube["RANGO_SEMANA"].unique().tolist()
    c_sel, c_b1, c_b2 = st.columns([2, 1, 1])
    with c_sel: sem_sel = st.selectbox("Semana:", semanas, label_visibility="collapsed")
    with c_b1: btn_sel = st.button("Consultar Selección", use_container_width=True)
    with c_b2: btn_act = st.button("SEMANA ACTUAL", type="primary", use_container_width=True)

    def stats(df_f, tit):
        st.markdown(f"#### {tit}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Venta Total", f"${df_f['VENTA_MXN'].sum():,.2f}")
        m2.metric("Comisiones", f"${df_f['COMISION_PAGADA_MXN'].sum():,.2f}")
        m3.metric("Ganancia", f"${df_f['GANANCIA_MXN'].sum():,.2f}")

    if btn_sel: stats(df_nube[df_nube["RANGO_SEMANA"] == sem_sel], sem_sel)
    if btn_act: stats(df_nube[df_nube["RANGO_SEMANA"] == rango_actual], "Semana Actual")
