import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Gestor Ventas Lola v32", layout="wide")

st.title("🚀 Control de Ventas - Lola")

conn = st.connection("gsheets", type=GSheetsConnection)

def lectura_segura():
    for i in range(3):
        try: return conn.read(ttl=0)
        except Exception: time.sleep(1)
    return pd.DataFrame()

df_nube = lectura_segura()

hoy = datetime.now()
inicio_semana = hoy - timedelta(days=hoy.weekday())
fin_semana = inicio_semana + timedelta(days=6)
rango_actual = f"{inicio_semana.strftime('%d/%m/%y')} al {fin_semana.strftime('%d/%m/%y')}"

# --- SIDEBAR: REGISTRO Y ACCIONES ---
with st.sidebar:
    st.header("📝 Nuevo Registro")
    nombre_prod = st.text_input("PRODUCTO")
    vendedoras = ["Fer", "Dany", "Barby", "Marta", "Eriberto", "Elena", "Julio", "Jaz", "Eli", "Viri", "Kari"]
    vendedora_sel = st.selectbox("VENDEDORA", vendedoras)
    compradora = st.text_input("COMPRADORA")
    
    usd_bruto_txt = st.text_input("COSTO USD", placeholder="Ej: 24")
    venta_txt = st.text_input("PRECIO DE VENTA (MXN)", placeholder="Ej: 1500")
    recibido_ini_txt = st.text_input("MONTO RECIBIDO INICIAL (MXN)", value="0")

    def limpiar_num(t):
        if not t: return 0.0
        try: return float(t.replace(',', '').replace('$', ''))
        except: return 0.0

    usd_bruto = limpiar_num(usd_bruto_txt)
    precio_venta = limpiar_num(venta_txt)
    monto_rec_ini = limpiar_num(recibido_ini_txt)

    # Cálculos internos
    costo_tot_mxn = usd_bruto * 27.40
    comi_mxn = usd_bruto * 7.40
    ganancia_mxn = precio_venta - costo_tot_mxn

    if monto_rec_ini <= 0: estado_ini = "🔴 Debe"
    elif monto_rec_ini < precio_venta: estado_ini = "🟡 Abonado"
    else: estado_ini = "🟢 Pagado"

    # --- BOTONES DE ACCIÓN ---
    c1, c2 = st.columns(2)
    with c1:
        btn_visualizar = st.button("🔍 CALCULAR", use_container_width=True)
    with c2:
        btn_guardar = st.button("✅ GUARDAR", type="primary", use_container_width=True)

    if btn_visualizar:
        st.info(f"**Vista Previa:**\n- Costo: ${costo_tot_mxn:,.2f}\n- Comisión: ${comi_mxn:,.2f}\n- Ganancia: ${ganancia_mxn:,.2f}\n- Estado: {estado_ini}")

    st.divider()
    
    # --- SECCIÓN ELIMINAR ---
    st.header("🗑️ Eliminar Registro")
    if not df_nube.empty:
        # Mostramos los últimos 10 para no saturar el selector
        opciones_del = [f"{i} - {df_nube.loc[i, 'PRODUCTO']}" for i in reversed(df_nube.index)]
        seleccion = st.selectbox("Selecciona ID:", opciones_del)
        
        if st.button("ELIMINAR SELECCIONADO", use_container_width=True):
            st.session_state.confirm_del = True
            
        if st.session_state.get('confirm_del', False):
            st.error("¿Estás seguro?")
            col_si, col_no = st.columns(2)
            if col_si.button("SÍ, BORRAR", type="primary"):
                idx_to_drop = int(seleccion.split(" - ")[0])
                df_nueva = df_nube.drop(idx_to_drop).reset_index(drop=True)
                conn.update(data=df_nueva)
                st.session_state.confirm_del = False
                st.cache_data.clear()
                st.rerun()
            if col_no.button("CANCELAR"):
                st.session_state.confirm_del = False
                st.rerun()

# --- LÓGICA DE GUARDADO ---
if btn_guardar:
    if nombre_prod and usd_bruto > 0:
        nuevo = pd.DataFrame([{
            "FECHA_REGISTRO": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "PRODUCTO": nombre_prod, "VENDEDORA": vendedora_sel, "COMPRADORA": compradora,
            "COSTO_USD": usd_bruto, "COMISION_PAGADA_MXN": comi_mxn, "COSTO_TOTAL_MXN": costo_tot_mxn,
            "PRECIO_VENTA": precio_venta, "GANANCIA_MXN": ganancia_mxn, "RANGO_SEMANA": rango_actual,
            "ESTADO_PAGO": estado_ini, "MONTO_RECIBIDO": monto_rec_ini
        }])
        conn.update(data=pd.concat([df_nube, nuevo], ignore_index=True))
        st.cache_data.clear()
        st.success("¡Guardado en la nube!")
        time.sleep(1)
        st.rerun()
    else:
        st.sidebar.warning("Faltan datos (Producto o Costo)")

# --- HISTORIAL Y COBRANZA ---
st.subheader("📋 Historial y Cobranza")
if not df_nube.empty:
    df_visual = df_nube.copy()
    df_visual["PENDIENTE"] = df_visual["PRECIO_VENTA"] - df_visual["MONTO_RECIBIDO"]
    
    edited_df = st.data_editor(
        df_visual.sort_index(ascending=False),
        column_config={
            "ESTADO_PAGO": st.column_config.SelectboxColumn("ESTADO", options=["🔴 Debe", "🟡 Abonado", "🟢 Pagado"]),
            "MONTO_RECIBIDO": st.column_config.NumberColumn("RECIBIDO", format="$%.2f"),
            "PENDIENTE": st.column_config.NumberColumn("POR COBRAR", format="$%.2f")
        },
        disabled=[c for c in df_visual.columns if c not in ["ESTADO_PAGO", "MONTO_RECIBIDO"]],
        use_container_width=True, key="ed_v32"
    )

    if st.button("💾 ACTUALIZAR PAGOS DE LA TABLA"):
        for idx in edited_df.index:
            if edited_df.at[idx, "ESTADO_PAGO"] == "🟢 Pagado":
                edited_df.at[idx, "MONTO_RECIBIDO"] = edited_df.at[idx, "PRECIO_VENTA"]
        
        columnas_base = ["FECHA_REGISTRO", "PRODUCTO", "VENDEDORA", "COMPRADORA", "COSTO_USD", "COMISION_PAGADA_MXN", "COSTO_TOTAL_MXN", "PRECIO_VENTA", "GANANCIA_MXN", "RANGO_SEMANA", "ESTADO_PAGO", "MONTO_RECIBIDO"]
        conn.update(data=edited_df[columnas_base].sort_index())
        st.cache_data.clear()
        st.rerun()

# --- REPORTES ---
st.divider()
st.subheader("💰 Resumen Financiero")
if not df_nube.empty:
    semanas = df_nube["RANGO_SEMANA"].unique().tolist()
    sem_sel = st.selectbox("Semana:", semanas)
    df_sem = df_nube[df_nube["RANGO_SEMANA"] == sem_sel]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ventas", f"${df_sem['PRECIO_VENTA'].sum():,.2f}")
    m2.metric("Comisiones", f"${df_sem['COMISION_PAGADA_MXN'].sum():,.2f}")
    m3.metric("Ganancia", f"${df_sem['GANANCIA_MXN'].sum():,.2f}")
    m4.metric("Por Cobrar", f"${(df_sem['PRECIO_VENTA'].sum() - df_sem['MONTO_RECIBIDO'].sum()):,.2f}")

    st.markdown("#### Rendimiento por Vendedora")
    resumen_vend = df_sem.groupby("VENDEDORA").agg({"PRODUCTO": "count", "PRECIO_VENTA": "sum"}).rename(columns={"PRODUCTO": "Cantidad", "PRECIO_VENTA": "Total $"})
    st.table(resumen_vend)