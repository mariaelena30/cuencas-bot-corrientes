"""
Dashboard en Tiempo Real: Monitoreo del Fenómeno El Niño y Cuencas de Corrientes
Estilo Visual: Franja Morada (Púrpura / Violeta / Lavanda)
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

# Configuración general
st.set_page_config(
    page_title="Monitoreo Cuencas Corrientes | Franja Morada",
    page_icon="💜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados Franja Morada
st.markdown("""
<style>
    /* Tipografía y Banner Superior */
    .franja-banner {
        background: linear-gradient(135deg, #4A148C 0%, #7B1FA2 50%, #9C27B0 100%);
        padding: 24px;
        border-radius: 12px;
        color: #ffffff;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(106, 27, 154, 0.25);
    }
    .franja-title {
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
        color: #FFFFFF;
        letter-spacing: -0.5px;
    }
    .franja-subtitle {
        font-size: 1.1rem;
        color: #E1BEE7;
        margin-top: 6px;
        font-weight: 500;
    }
    
    /* Tarjetas Métricas */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border-top: 4px solid #7B1FA2;
        padding: 14px;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(74, 20, 140, 0.08);
    }
    
    /* Cajas informativas */
    .info-card-morada {
        background: #F3E5F5;
        border-left: 5px solid #6A1B9A;
        padding: 14px 18px;
        border-radius: 8px;
        color: #38006B;
        font-size: 0.95rem;
    }
    
    /* Botones y badges */
    .badge-morado {
        background: linear-gradient(90deg, #7B1FA2, #9C27B0);
        color: white;
        padding: 3px 10px;
        border-radius: 15px;
        font-size: 0.75rem;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# BANNER SUPERIOR
st.markdown("""
<div class="franja-banner">
    <div class="franja-title">💜 Monitoreo de Cuencas & Fenómeno El Niño</div>
    <div class="franja-subtitle">Provincia de Corrientes | Sistema de Alerta Temprana en Tiempo Real (Ríos Paraná y Uruguay)</div>
</div>
""", unsafe_allow_html=True)

# BARRA LATERAL
with st.sidebar:
    st.markdown("""
        <div style="text-align: center; margin-bottom: 15px;">
            <div style="background: #7B1FA2; color: white; border-radius: 50%; width: 55px; height: 55px; display: inline-flex; align-items: center; justify-content: center; font-size: 26px; font-weight: bold; box-shadow: 0 3px 8px rgba(123, 31, 162, 0.4);">
                FM
            </div>
            <h3 style="color: #4A148C; margin-top: 10px; font-weight: 700;">Panel de Control</h3>
        </div>
    """, unsafe_allow_html=True)
    
    cuenca_filter = st.selectbox(
        "Filtrar por Río/Cuenca:",
        ["Todos los Ríos", "Río Paraná", "Río Uruguay"]
    )
    
    st.divider()
    st.markdown("**📡 Fuentes Integradas:**")
    st.markdown("• Prefectura Naval Argentina (PNA)")
    st.markdown("• NOAA Climate Prediction Center")
    st.markdown("• Instituto Correntino del Agua (ICAA)")
    st.markdown("• INA / SMN")
    
    st.divider()
    if st.button("🔄 Actualizar Datos"):
        st.cache_data.clear()
        st.toast("Datos actualizados correctamente", icon="💜")

# 1. ESTADO DEL FENÓMENO EL NIÑO (ENSO)
enso_data = fetch_enso_status()

st.markdown('<h3 style="color:#4A148C; font-weight:700;">🌐 Estado Global del Fenómeno El Niño (ENSO)</h3>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        label="Fase Climática",
        value=enso_data["phase"].split()[0] + " " + enso_data["phase"].split()[1],
        delta=f"Intensidad: {enso_data['severity']}"
    )
with c2:
    st.metric(
        label="Anomalía Niño 3.4 (SST)",
        value=f"{enso_data['anom']:+.2f} °C",
        delta="Umbral >= +0.5°C"
    )
with c3:
    st.metric(
        label="Período de Medición",
        value=enso_data["period"]
    )
with c4:
    impact_text = "Riesgo alto de crecidas e inundaciones en el Litoral" if enso_data["anom"] >= 0.5 else "Bajo riesgo de crecidas"
    st.markdown(f"""
    <div class="info-card-morada">
        <b>Impacto Corrientes:</b><br>{impact_text}
    </div>
    """, unsafe_allow_html=True)

st.write("")

# 2. CARGA DE DATOS HIDROMÉTRICOS
df_rios = fetch_river_heights()

if cuenca_filter != "Todos los Ríos":
    df_rios = df_rios[df_rios["Río"] == cuenca_filter]

total_puertos = len(df_rios)
en_alerta = len(df_rios[df_rios["Estado"] == "ALERTA"])
en_evac = len(df_rios[df_rios["Estado"] == "EVACUACIÓN"])
en_normal = len(df_rios[df_rios["Estado"] == "NORMAL"])

# 3. SEMÁFORO Y MAPA INTERACTIVO
col_left, col_right = st.columns([1.1, 1.4])

with col_left:
    st.markdown('<h3 style="color:#4A148C; font-weight:700;">🚨 Semáforo de Cuencas</h3>', unsafe_allow_html=True)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("🟢 Normal", f"{en_normal}/{total_puertos}")
    m2.metric("🟡 Alerta", f"{en_alerta}/{total_puertos}")
    m3.metric("🔴 Evacuación", f"{en_evac}/{total_puertos}")
    
    st.markdown('<h4 style="color:#6A1B9A; margin-top:15px;">Estado por Puerto</h4>', unsafe_allow_html=True)
    for _, row in df_rios.iterrows():
        color = row["BadgeColor"]
        st.markdown(
            f"""
            <div style="background-color: #FFFFFF; border-left: 6px solid {color}; border-right: 2px solid #EDE7F6; padding: 10px 14px; margin-bottom: 10px; border-radius: 8px; box-shadow: 0 2px 5px rgba(106, 27, 154, 0.05);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:700; color:#2A0845;">{row['Puerto']}</span>
                    <span style="background-color:{color}; color:white; padding:2px 10px; border-radius:12px; font-size:0.75rem; font-weight:bold;">{row['Estado']}</span>
                </div>
                <div style="font-size:0.9rem; color:#555; margin-top:4px;">
                    Altura: <b style="color:#4A148C;">{row['Altura (m)']} m</b> | Tendencia: {row['Tendencia']} ({row['Variación 24h (m)']:+.2f} m)
                </div>
            </div>
            """, 
            unsafe_allow_html=True
        )

with col_right:
    st.markdown('<h3 style="color:#4A148C; font-weight:700;">🗺️ Mapa Hidrológico de Corrientes</h3>', unsafe_allow_html=True)
    
    # Mapa Folium centrado
    m = folium.Map(location=MAP_CENTER_CORRIENTES, zoom_start=7, tiles="CartoDB positron")
    
    for _, row in df_rios.iterrows():
        if row["Estado"] == "EVACUACIÓN":
            color = "red"
            icon = "exclamation-triangle"
        elif row["Estado"] == "ALERTA":
            color = "orange"
            icon = "warning"
        else:
            color = "purple" # Marcador morado para estado normal
            icon = "tint"
            
        popup_html = f"""
        <div style="font-family:sans-serif; color:#38006B;">
            <b style="color:#6A1B9A; font-size:1.05rem;">{row['Puerto']}</b><br>
            <b>Río:</b> {row['Río']}<br>
            <b>Altura:</b> <span style="font-size:1.1rem; font-weight:bold; color:#4A148C;">{row['Altura (m)']} m</span><br>
            <b>Nivel Alerta:</b> {row['Nivel Alerta (m)']} m | <b>Evac:</b> {row['Nivel Evacuación (m)']} m<br>
            <b>Tendencia:</b> {row['Tendencia']}
        </div>
        """
        
        folium.Marker(
            location=[row["Lat"], row["Lon"]],
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"{row['Puerto']}: {row['Altura (m)']} m",
            icon=folium.Icon(color=color, icon=icon, prefix="fa")
        ).add_to(m)
        
    st_folium(m, width="100%", height=480)

st.write("")

# 4. GRÁFICOS CON PALETA MORADA
st.markdown('<h3 style="color:#4A148C; font-weight:700;">📈 Análisis de Tendencias y Precipitaciones</h3>', unsafe_allow_html=True)

col_g1, col_g2 = st.columns(2)

with col_g1:
    puerto_seleccionado = st.selectbox(
        "Seleccionar Puerto para Historial:",
        list(PUERTOS_CORRIENTES.keys()),
        index=3 # Corrientes Capital
    )
    
    df_hist = fetch_historical_series(puerto_seleccionado, dias=30)
    
    fig_hist = go.Figure()
    
    # Línea morada para la altura registrada
    fig_hist.add_trace(go.Scatter(
        x=df_hist["Fecha"], y=df_hist["Altura"],
        mode="lines+markers", name="Altura Registrada",
        line=dict(color="#7B1FA2", width=3),
        marker=dict(size=6, color="#4A148C")
    ))
    fig_hist.add_trace(go.Scatter(
        x=df_hist["Fecha"], y=df_hist["Alerta"],
        mode="lines", name="Nivel Alerta",
        line=dict(color="#FFA000", dash="dash", width=2)
    ))
    fig_hist.add_trace(go.Scatter(
        x=df_hist["Fecha"], y=df_hist["Evacuacion"],
        mode="lines", name="Nivel Evacuación",
        line=dict(color="#D32F2F", dash="dot", width=2)
    ))
    
    fig_hist.update_layout(
        title=dict(text=f"Evolución Hidrométrica - {puerto_seleccionado}", font=dict(color="#4A148C", size=16)),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FAF7FC",
        xaxis=dict(title="Fecha", gridcolor="#EDE7F6"),
        yaxis=dict(title="Altura del Río (m)", gridcolor="#EDE7F6"),
        hovermode="x unified",
        margin=dict(l=20, r=20, t=45, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_hist, use_container_width=True)

with col_g2:
    st.markdown('<h4 style="color:#6A1B9A; margin-top:5px;">🌧️ Pronóstico de Lluvias (Próximos 7 días)</h4>', unsafe_allow_html=True)
    df_rain = fetch_weather_and_rain()
    
    # Gráfico de barras con escala degradada en morados
    fig_rain = px.bar(
        df_rain,
        x="Fecha",
        y="Precipitación (mm)",
        text="Precipitación (mm)",
        title="Lluvias Acumuladas Previstas en Cuencas de Corrientes",
        color="Precipitación (mm)",
        color_continuous_scale=["#E1BEE7", "#BA68C8", "#8E24AA", "#4A148C"]
    )
    fig_rain.update_traces(texttemplate='%{text:.1f} mm', textposition='outside')
    fig_rain.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FAF7FC",
        title=dict(font=dict(color="#4A148C", size=16)),
        xaxis=dict(title="Día", gridcolor="#EDE7F6"),
        yaxis=dict(title="Milímetros (mm)", gridcolor="#EDE7F6"),
        coloraxis_colorbar=dict(title="mm"),
        margin=dict(l=20, r=20, t=45, b=20)
    )
    st.plotly_chart(fig_rain, use_container_width=True)

# 5. TABLA DE DATOS
with st.expander("📋 Ver Tabla Completa de Datos Hidrométricos"):
    st.dataframe(
        df_rios[["Puerto", "Río", "Cuenca", "Altura (m)", "Variación 24h (m)", "Tendencia", "Nivel Alerta (m)", "Nivel Evacuación (m)", "Estado"]],
        use_container_width=True,
        hide_index=True
    )
