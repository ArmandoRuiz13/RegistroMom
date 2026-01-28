import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Gestor Ventas Lola v29", layout="wide")

st.title("🚀 Control de Ventas - Lola")

conn = st.connection("gsheets", type=GSheetsConnection)

def lectura_segura():
    for i in range(3):
        try: return conn.read(ttl=0)
        except Exception: time.sleep(1)
    return pd.DataFrame()

# --- DATOS ACTUALES ---
df_nube = lectura_segura()

# --- RANGO SEMANAL ACTUAL ---
hoy = datetime.now()
inicio_semana = hoy - timedelta(days=hoy.weekday())
fin_semana = inicio_semana + timedelta(days=6)
rango_actual = f"{inicio_semana.strftime('%d/%m/%y')} al {fin_semana.strftime('%d/%m/%y')}"

# --- SIDEBAR: REGISTRO ---
with st.sidebar:
    st.header("📝 Nuevo Registro")
    
    nombre_prod = st.text_input("PRODUCTO", placeholder="Ej: Tenis Jordan")
    
    vendedoras = ["Fer", "Dany", "Barby", "Marta", "Eriberto", "Elena", "Julio", "Jaz", "Eli", "Viri", "Kari"]
    vendedora_sel = st.selectbox("VENDEDORA", vendedoras)
    
    compradora = st.text_input("COMPRADORA (Nombre o Tel)")
    
    usd_bruto_txt = st.text_input("COSTO USD", placeholder="Ej: 24")
    venta_txt = st.text_input("PRECIO DE VENTA (MXN)", placeholder="Ej: 1500")

    def limpiar_num(t):
        if not t: return 0.0
        try: return float(t.replace(',', '').replace('$', ''))
        except: return 0.0

    usd_bruto = limpiar_num(usd_bruto_txt)
    precio_venta = limpiar_num(venta_txt)

    # --- NUEVA LÓGICA DE COMISIÓN ---
    # Costo Total con el dólar a 27.40
    costo_tot_mxn = usd_bruto * 27.40
    
    # Comisión = El excedente de los 7.40 pesos sobre el dólar base de 20
    comi_mxn = usd_bruto * 7.40
    
    # Ganancia = Precio Venta - Costo Total (27.40)
    ganancia_mxn = precio_venta - costo_tot_mxn

    if st.button("CALCULAR 🔍", use_container_width=True):
        st.info(f"Costo Total: ${costo_tot_mxn:,.2f}\n\nComisión ($7.40 x USD): ${comi_mxn:,.2f}\n\nGanancia: ${ganancia_mxn:,.2f}")

    btn_guardar = st.button("GUARDAR EN NUBE ✅", use_container_width=True, type="primary")

    st.divider()
    if not df_nube.empty:
        opciones_del = [f"{i} - {df_nube.loc[i, 'PRODUCTO']}" for i in reversed(df_nube.index)]
        seleccion = st.selectbox("ID a borrar:", opciones_del)
        if st.button("ELIMINAR SELECCIONADO"):
            st.session_state.confirm_delete = True
        
        if st.session_state.get('confirm_delete', False):
            st.error("¿Confirmas borrado?")
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
if btn_guardar and nombre_prod and usd_bruto > 0:
    nuevo = pd.DataFrame([{
        "FECHA_REGISTRO": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "PRODUCTO": nombre_prod,
        "VENDEDORA": vendedora_sel,
        "COMPRADORA": compradora,
        "COSTO_USD": usd_bruto,
        "COMISION_PAGADA_MXN": comi_mxn,
        "COSTO_TOTAL_MXN": costo_tot_mxn,
        "PRECIO_VENTA": precio_venta,
        "GANANCIA_MXN": ganancia_mxn,
        "RANGO_SEMANA": rango_actual,
        "ESTADO_PAGO": "🔴 Debe",
        "MONTO_RECIBIDO": 0.0,
        "FECHA": datetime.now().strftime("%d/%m/%Y")
    }])
    
    df_actualizado = pd.concat([df_nube, nuevo], ignore_index=True)
    conn.update(data=df_actualizado)
    st.cache_data.clear()
    st.rerun()

# --- HISTORIAL ---
st.subheader("📋 Historial y Cobranza")
if not df_nube.empty:
    df_para_editar = df_nube.sort_index(ascending=False)
    
    edited_df = st.data_editor(
        df_para_editar,
        column_config={
            "ESTADO_PAGO": st.column_config.SelectboxColumn("ESTADO", options=["🔴 Debe", "🟡 Abonado", "🟢 Pagado"]),
            "MONTO_RECIBIDO": st.column_config.NumberColumn("RECIBIDO", format="$%.2f")
        },
        disabled=[c for c in df_nube.columns if c not in ["ESTADO_PAGO", "MONTO_RECIBIDO"]],
        use_container_width=True, key="ed_v29"
    )

    if st.button("💾 GUARDAR CAMBIOS DE TABLA"):
        for idx in edited_df.index:
            if edited_df.at[idx, "ESTADO_PAGO"] == "🟢 Pagado":
                edited_df.at[idx, "MONTO_RECIBIDO"] = edited_df.at[idx, "PRECIO_VENTA"]
        
        conn.update(data=edited_df.sort_index())
        st.success("¡Información actualizada!")
        st.cache_data.clear()
        st.rerun()

# --- REPORTES ---
st.divider()
st.subheader("💰 Resumen Financiero")
if not df_nube.empty:
    semanas = df_nube["RANGO_SEMANA"].unique().tolist()
    c_sel, c_b1, c_b2 = st.columns([2, 1, 1])
    with c_sel: sem_sel = st.selectbox("Seleccionar Semana:", semanas, label_visibility="collapsed")
    with c_b1: btn_sel = st.button("Ver Selección", use_container_width=True)
    with c_b2: btn_act = st.button("VER ACTUAL", type="primary", use_container_width=True)

    def stats(df_f, tit):
        st.markdown(f"#### {tit}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Ventas", f"${df_f['PRECIO_VENTA'].sum():,.2f}")
        m2.metric("Comisiones (Sobreprecio)", f"${df_f['COMISION_PAGADA_MXN'].sum():,.2f}")
        m3.metric("Ganancia Neta", f"${df_f['GANANCIA_MXN'].sum():,.2f}")

    if btn_sel: stats(df_nube[df_nube["RANGO_SEMANA"] == sem_sel], sem_sel)
    if btn_act: stats(df_nube[df_nube["RANGO_SEMANA"] == rango_actual], "Semana Actual")