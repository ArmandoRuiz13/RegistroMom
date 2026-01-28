import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Gestor Ventas Lola v31", layout="wide")

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

# --- SIDEBAR: REGISTRO ---
with st.sidebar:
    st.header("📝 Nuevo Registro")
    nombre_prod = st.text_input("PRODUCTO")
    vendedoras = ["Fer", "Dany", "Barby", "Marta", "Eriberto", "Elena", "Julio", "Jaz", "Eli", "Viri", "Kari"]
    vendedora_sel = st.selectbox("VENDEDORA", vendedoras)
    compradora = st.text_input("COMPRADORA")
    usd_bruto_txt = st.text_input("COSTO USD", placeholder="24")
    venta_txt = st.text_input("PRECIO DE VENTA (MXN)", placeholder="1500")
    recibido_ini_txt = st.text_input("MONTO RECIBIDO INICIAL (MXN)", value="0")

    def limpiar_num(t):
        if not t: return 0.0
        try: return float(t.replace(',', '').replace('$', ''))
        except: return 0.0

    usd_bruto = limpiar_num(usd_bruto_txt)
    precio_venta = limpiar_num(venta_txt)
    monto_rec_ini = limpiar_num(recibido_ini_txt)

    # Cálculos
    costo_tot_mxn = usd_bruto * 27.40
    comi_mxn = usd_bruto * 7.40
    ganancia_mxn = precio_venta - costo_tot_mxn

    # Estado Automático
    if monto_rec_ini <= 0: estado_ini = "🔴 Debe"
    elif monto_rec_ini < precio_venta: estado_ini = "🟡 Abonado"
    else: estado_ini = "🟢 Pagado"

    btn_guardar = st.button("GUARDAR EN NUBE ✅", use_container_width=True, type="primary")

if btn_guardar and nombre_prod and usd_bruto > 0:
    nuevo = pd.DataFrame([{
        "FECHA_REGISTRO": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "PRODUCTO": nombre_prod, "VENDEDORA": vendedora_sel, "COMPRADORA": compradora,
        "COSTO_USD": usd_bruto, "COMISION_PAGADA_MXN": comi_mxn, "COSTO_TOTAL_MXN": costo_tot_mxn,
        "PRECIO_VENTA": precio_venta, "GANANCIA_MXN": ganancia_mxn, "RANGO_SEMANA": rango_actual,
        "ESTADO_PAGO": estado_ini, "MONTO_RECIBIDO": monto_rec_ini
    }])
    conn.update(data=pd.concat([df_nube, nuevo], ignore_index=True))
    st.cache_data.clear()
    st.rerun()

# --- HISTORIAL Y PENDIENTES ---
st.subheader("📋 Historial y Cobranza")
if not df_nube.empty:
    df_visual = df_nube.copy()
    # Calculamos el pendiente solo para visualización
    df_visual["PENDIENTE"] = df_visual["PRECIO_VENTA"] - df_visual["MONTO_RECIBIDO"]
    
    df_para_editar = df_visual.sort_index(ascending=False)
    
    edited_df = st.data_editor(
        df_para_editar,
        column_config={
            "ESTADO_PAGO": st.column_config.SelectboxColumn("ESTADO", options=["🔴 Debe", "🟡 Abonado", "🟢 Pagado"]),
            "MONTO_RECIBIDO": st.column_config.NumberColumn("RECIBIDO", format="$%.2f"),
            "PENDIENTE": st.column_config.NumberColumn("POR COBRAR", format="$%.2f", help="Lo que falta para liquidar")
        },
        disabled=[c for c in df_visual.columns if c not in ["ESTADO_PAGO", "MONTO_RECIBIDO"]],
        use_container_width=True, key="ed_v31"
    )

    if st.button("💾 GUARDAR CAMBIOS DE TABLA"):
        for idx in edited_df.index:
            if edited_df.at[idx, "ESTADO_PAGO"] == "🟢 Pagado":
                edited_df.at[idx, "MONTO_RECIBIDO"] = edited_df.at[idx, "PRECIO_VENTA"]
        
        # Solo guardamos las 12 columnas originales (sin el "PENDIENTE" calculado)
        columnas_base = ["FECHA_REGISTRO", "PRODUCTO", "VENDEDORA", "COMPRADORA", "COSTO_USD", "COMISION_PAGADA_MXN", "COSTO_TOTAL_MXN", "PRECIO_VENTA", "GANANCIA_MXN", "RANGO_SEMANA", "ESTADO_PAGO", "MONTO_RECIBIDO"]
        conn.update(data=edited_df[columnas_base].sort_index())
        st.cache_data.clear()
        st.rerun()

# --- REPORTES ---
st.divider()
st.subheader("💰 Resumen Semanal")
if not df_nube.empty:
    semanas = df_nube["RANGO_SEMANA"].unique().tolist()
    sem_sel = st.selectbox("Selecciona Semana:", semanas)
    df_sem = df_nube[df_nube["RANGO_SEMANA"] == sem_sel]

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### Totales")
        st.metric("Ventas Totales", f"${df_sem['PRECIO_VENTA'].sum():,.2f}")
        st.metric("Comisiones", f"${df_sem['COMISION_PAGADA_MXN'].sum():,.2f}")
        st.metric("Ganancia Neta", f"${df_sem['GANANCIA_MXN'].sum():,.2f}")
        st.warning(f"Pendiente por cobrar: ${ (df_sem['PRECIO_VENTA'].sum() - df_sem['MONTO_RECIBIDO'].sum()):,.2f}")

    with col2:
        st.markdown("#### Rendimiento por Vendedora")
        resumen_vend = df_sem.groupby("VENDEDORA").agg({
            "PRODUCTO": "count",
            "PRECIO_VENTA": "sum"
        }).rename(columns={"PRODUCTO": "Cantidad", "PRECIO_VENTA": "Total Vendido"})
        st.dataframe(resumen_vend, use_container_width=True)