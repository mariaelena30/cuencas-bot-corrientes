"""
Dashboard en Tiempo Real: Monitoreo del Fenómeno El Niño y Cuencas de Corrientes
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import pandas as pd
from datetime import datetime

from config import PUERTOS_CORRIENTES, MAP_CENTER_CORRIENTES
from data_fetcher import (
    fetch_enso_status, 
    fetch_river_heights, 
    fetch_historical_series, 
    fetch_weather_and_rain
)

# Configuración de página
st.set_page_config(
    page_title="Monitoreo El Niño & Cuencas Corrientes",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo personalizado CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #0b3c5d;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #555;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-left: 5px solid #0b3c5d;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .alert-box {
        padding: 12px;
        border-radius: 6px;
        font-weight: 600;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Encabezado principal
st.markdown('<div class="main-header">🌊 Monitoreo Hidrometeorológico & Fenómeno El Niño</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Provincia de Corrientes | Sistema de Alerta Temprana de Cuencas (Ríos Paraná y Uruguay)</div>', unsafe_allow_html=True)

# Barra lateral de control
with st.sidebar:
    st.image("https://img.icons8.com/color/96/water.png", width=70)
    st.header("⚙️ Filtros y Opciones")
    cuenca_filter = st.selectbox(
        "Filtrar por Río/Cuenca:",
        ["Todos los Ríos", "Río Paraná", "Río Uruguay"]
    )
    
    st.divider()
    st.markdown("**Fuente de Datos:**")
    st.markdown("• Prefectura Naval Argentina (PNA)")
    st.markdown("• NOAA Climate Prediction Center")
    st.markdown("• Instituto Correntino del Agua (ICAA)")
    st.markdown("• INA / SMN")
    
    st.divider()
    if st.button("🔄 Actualizar Datos Ahora"):
        st.cache_data.clear()
        st.toast("Datos actualizados con éxito", icon="✅")

# 1. SECCIÓN: ESTADO DEL FENÓMENO EL NIÑO (ENSO)
enso_data = fetch_enso_status()

st.subheader("🌐 Estado Global del Fenómeno El Niño (ENSO)")
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        label="Fase Climática Actual",
        value=enso_data["phase"].split()[0] + " " + enso_data["phase"].split()[1],
        delta=f"Intensidad: {enso_data['severity']}"
    )
with c2:
    st.metric(
        label="Anomalía Niño 3.4 (SST)",
        value=f"{enso_data['anom']:+.2f} °C",
        delta="Umbral El Niño >= +0.5°C"
    )
with c3:
    st.metric(
        label="Periodo Evaluado",
        value=enso_data["period"]
    )
with c4:
    impact_text = "Alto riesgo de crecidas e inundaciones en Corrientes" if enso_data["anom"] >= 0.5 else "Riesgo de bajantes y sequías"
    st.info(f"**Impacto Regional:** {impact_text}")

st.divider()

# 2. CARGA DE DATOS DE RÍOS
df_rios = fetch_river_heights()

if cuenca_filter != "Todos los Ríos":
    df_rios = df_rios[df_rios["Río"] == cuenca_filter]

# Resumen de estados
total_puertos = len(df_rios)
en_alerta = len(df_rios[df_rios["Estado"] == "ALERTA"])
en_evac = len(df_rios[df_rios["Estado"] == "EVACUACIÓN"])
en_normal = len(df_rios[df_rios["Estado"] == "NORMAL"])

# 3. SECCIÓN: SEMÁFORO DE ALERTA Y MAPA INTERACTIVO
col_left, col_right = st.columns([1.1, 1.4])

with col_left:
    st.subheader("🚨 Semáforo de Cuencas")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("🟢 Normal", f"{en_normal}/{total_puertos}")
    m2.metric("🟡 Alerta", f"{en_alerta}/{total_puertos}")
    m3.metric("🔴 Evacuación", f"{en_evac}/{total_puertos}")
    
    st.markdown("### Estado por Puerto")
    for _, row in df_rios.iterrows():
        color = row["BadgeColor"]
        st.markdown(
            f"""
            <div style="background-color: #ffffff; border-left: 6px solid {color}; padding: 8px 12px; margin-bottom: 8px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong>{row['Puerto']}</strong>
                    <span style="background-color:{color}; color:white; padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:bold;">{row['Estado']}</span>
                </div>
                <div style="font-size:0.9rem; color:#444; margin-top:4px;">
                    Altura: <b>{row['Altura (m)']} m</b> | Tendencia: {row['Tendencia']} ({row['Variación 24h (m)']:+.2f} m)
                </div>
            </div>
            """, 
            unsafe_allow_html=True
        )

with col_right:
    st.subheader("🗺️ Mapa Hidrológico de Corrientes")
    
    # Crear mapa Folium centrado en Corrientes
    m = folium.Map(location=MAP_CENTER_CORRIENTES, zoom_start=7, tiles="CartoDB positron")
    
    for _, row in df_rios.iterrows():
        if row["Estado"] == "EVACUACIÓN":
            color = "red"
            icon = "exclamation-triangle"
        elif row["Estado"] == "ALERTA":
            color = "orange"
            icon = "warning"
        else:
            color = "green"
            icon = "tint"
            
        popup_html = f"""
        <b>{row['Puerto']}</b><br>
        Río: {row['Río']}<br>
        Altura: <b>{row['Altura (m)']} m</b><br>
        Alerta: {row['Nivel Alerta (m)']} m | Evac: {row['Nivel Evacuación (m)']} m<br>
        Tendencia: {row['Tendencia']}
        """
        
        folium.Marker(
            location=[row["Lat"], row["Lon"]],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{row['Puerto']}: {row['Altura (m)']} m ({row['Estado']})",
            icon=folium.Icon(color=color, icon=icon, prefix="fa")
        ).add_to(m)
        
    st_folium(m, width="100%", height=480)

st.divider()

# 4. SECCIÓN: GRÁFICOS TEMPORALES Y PLUVIOMETRÍA
st.subheader("📈 Análisis de Tendencias y Precipitaciones")

col_g1, col_g2 = st.columns(2)

with col_g1:
    puerto_seleccionado = st.selectbox(
        "Seleccionar Puerto para Historial:",
        list(PUERTOS_CORRIENTES.keys()),
        index=3 # Corrientes Capital
    )
    
    df_hist = fetch_historical_series(puerto_seleccionado, dias=30)
    
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(
        x=df_hist["Fecha"], y=df_hist["Altura"],
        mode="lines+markers", name="Altura Registrada",
        line=dict(color="#007bff", width=2.5)
    ))
    fig_hist.add_trace(go.Scatter(
        x=df_hist["Fecha"], y=df_hist["Alerta"],
        mode="lines", name="Nivel de Alerta",
        line=dict(color="#ffc107", dash="dash", width=2)
    ))
    fig_hist.add_trace(go.Scatter(
        x=df_hist["Fecha"], y=df_hist["Evacuacion"],
        mode="lines", name="Nivel de Evacuación",
        line=dict(color="#dc3545", dash="dot", width=2)
    ))
    
    fig_hist.update_layout(
        title=f"Evolución Hidrométrica - {puerto_seleccionado}",
        xaxis_title="Fecha",
        yaxis_title="Altura del Río (metros)",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_hist, use_container_width=True)

with col_g2:
    st.markdown("#### 🌧️ Pronóstico de Lluvias (Próximos 7 días)")
    df_rain = fetch_weather_and_rain()
    
    fig_rain = px.bar(
        df_rain,
        x="Fecha",
        y="Precipitación (mm)",
        text="Precipitación (mm)",
        title="Lluvias Acumuladas Previstas en Cuencas de Corrientes",
        color="Precipitación (mm)",
        color_continuous_scale="Blues"
    )
    fig_rain.update_traces(texttemplate='%{text:.1f} mm', textposition='outside')
    fig_rain.update_layout(
        xaxis_title="Día",
        yaxis_title="Milímetros (mm)",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig_rain, use_container_width=True)

# 5. TABLA COMPLETA DE DATOS
with st.expander("📋 Ver Tabla Completa de Datos Hidrométricos"):
    st.dataframe(
        df_rios[["Puerto", "Río", "Cuenca", "Altura (m)", "Variación 24h (m)", "Tendencia", "Nivel Alerta (m)", "Nivel Evacuación (m)", "Estado"]],
        use_container_width=True,
        hide_index=True
    )
