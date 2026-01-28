import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Gestor Ventas Lola v34", layout="wide")

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
    
    # --- VENDEDORAS CON OPCIÓN NUEVA ---
    lista_vendedoras = ["Fer", "Dany", "Barby", "Marta", "Eriberto", "Elena", "Julio", "Jaz", "Eli", "Viri", "Kari", "NUEVA"]
    vendedora_sel = st.selectbox("VENDEDORA", lista_vendedoras)
    
    if vendedora_sel == "NUEVA":
        vendedora_final = st.text_input("Nombre de la nueva vendedora:")
    else:
        vendedora_final = vendedora_sel
        
    compradora = st.text_input("COMPRADORA")
    
    usd_bruto_txt = st.text_input("COSTO USD", placeholder="Ej: 24")
    venta_txt = st.text_input("PRECIO DE VENTA (MXN)", placeholder="Ej: 1500")

    def limpiar_num(t):
        if not t: return 0.0
        try: return float(t.replace(',', '').replace('$', ''))
        except: return 0.0

    usd_bruto = limpiar_num(usd_bruto_txt)
    precio_venta = limpiar_num(venta_txt)
    
    # --- SUGERENCIA DE 50% ---
    if precio_venta > 0:
        st.caption(f"💡 **Sugerir pago (50%):** ${precio_venta/2:,.2f}")
    
    recibido_ini_txt = st.text_input("MONTO RECIBIDO INICIAL (MXN)", value="0")
    monto_rec_ini = limpiar_num(recibido_ini_txt)

    # Cálculos
    costo_tot_mxn = usd_bruto * 27.40
    comi_mxn = usd_bruto * 7.40
    ganancia_mxn = precio_venta - costo_tot_mxn

    if monto_rec_ini <= 0: estado_ini = "🔴 Debe"
    elif monto_rec_ini < precio_venta: estado_ini = "🟡 Abonado"
    else: estado_ini = "🟢 Pagado"

    c1, c2 = st.columns(2)
    with c1:
        btn_visualizar = st.button("🔍 CALCULAR", use_container_width=True)
    with c2:
        btn_guardar = st.button("✅ GUARDAR", type="primary", use_container_width=True)

    if btn_visualizar:
        st.info(f"**Vista Previa:**\n- Costo: ${costo_tot_mxn:,.2f}\n- Comisión: ${comi_mxn:,.2f}\n- Ganancia: ${ganancia_mxn:,.2f}\n- Estado: {estado_ini}")

    st.divider()
    st.header("🗑️ Eliminar Registro")
    if not df_nube.empty:
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
    if nombre_prod and usd_bruto > 0 and vendedora_final:
        nuevo = pd.DataFrame([{
            "FECHA_REGISTRO": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "PRODUCTO": nombre_prod, "VENDEDORA": vendedora_final, "COMPRADORA": compradora,
            "COSTO_USD": usd_bruto, "COMISION_PAGADA_MXN": comi_mxn, "COSTO_TOTAL_MXN": costo_tot_mxn,
            "PRECIO_VENTA": precio_venta, "GANANCIA_MXN": ganancia_mxn, "RANGO_SEMANA": rango_actual,
            "ESTADO_PAGO": estado_ini, "MONTO_RECIBIDO": monto_rec_ini
        }])
        conn.update(data=pd.concat([df_nube, nuevo], ignore_index=True))
        st.cache_data.clear()
        st.rerun()
    else:
        st.sidebar.warning("Faltan datos (Producto, Costo o Vendedora)")

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
        use_container_width=True, key="ed_v34"
    )

    if st.button("💾 ACTUALIZAR PAGOS"):
        for idx in edited_df.index:
            if edited_df.at[idx, "ESTADO_PAGO"] == "🟢 Pagado":
                edited_df.at[idx, "MONTO_RECIBIDO"] = edited_df.at[idx, "PRECIO_VENTA"]
        columnas_base = ["FECHA_REGISTRO", "PRODUCTO", "VENDEDORA", "COMPRADORA", "COSTO_USD", "COMISION_PAGADA_MXN", "COSTO_TOTAL_MXN", "PRECIO_VENTA", "GANANCIA_MXN", "RANGO_SEMANA", "ESTADO_PAGO", "MONTO_RECIBIDO"]
        conn.update(data=edited_df[columnas_base].sort_index())
        st.cache_data.clear()
        st.rerun()

# --- REPORTES (BAJO DEMANDA) ---
st.divider()
st.subheader("📊 Reportes y Resúmenes")
if not df_nube.empty:
    semanas = df_nube["RANGO_SEMANA"].unique().tolist()
    c_sel, b_sel, b_act = st.columns([2, 1, 1])
    with c_sel: sem_sel = st.selectbox("Elegir semana:", semanas, label_visibility="collapsed")
    with b_sel: btn_ver_sel = st.button("📊 VISUALIZAR SEMANA ELEGIDA", use_container_width=True)
    with b_act: btn_ver_act = st.button("🌟 VISUALIZAR SEMANA ACTUAL", use_container_width=True)

    def mostrar_reporte(df_f, titulo):
        st.markdown(f"### 📈 Reporte: {titulo}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ventas", f"${df_f['PRECIO_VENTA'].sum():,.2f}")
        m2.metric("Comisiones", f"${df_f['COMISION_PAGADA_MXN'].sum():,.2f}")
        m3.metric("Ganancia", f"${df_f['GANANCIA_MXN'].sum():,.2f}")
        m4.metric("Por Cobrar", f"${(df_f['PRECIO_VENTA'].sum() - df_f['MONTO_RECIBIDO'].sum()):,.2f}")
        
        st.markdown("#### Detalle por Vendedora")
        resumen = df_f.groupby("VENDEDORA").agg({"PRODUCTO": "count", "PRECIO_VENTA": "sum"}).rename(columns={"PRODUCTO": "Cantidad", "PRECIO_VENTA": "Vendido $"})
        st.table(resumen)

    if btn_ver_sel:
        mostrar_reporte(df_nube[df_nube["RANGO_SEMANA"] == sem_sel], sem_sel)
    
    if btn_ver_act:
        mostrar_reporte(df_nube[df_nube["RANGO_SEMANA"] == rango_actual], "Semana Actual")