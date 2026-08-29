"""
Configuración de puertos, estaciones y umbrales para Corrientes.
"""

PUERTOS_CORRIENTES = {
    "Ituzaingó (Río Paraná)": {
        "lat": -27.5833, "lon": -56.6833,
        "alerta": 3.50, "evacuacion": 4.00,
        "rio": "Paraná", "cuenca": "Alto Paraná"
    },
    "Itatí (Río Paraná)": {
        "lat": -27.2667, "lon": -58.2500,
        "alerta": 6.80, "evacuacion": 7.50,
        "rio": "Paraná", "cuenca": "Paraná Medio"
    },
    "Paso de la Patria (Río Paraná)": {
        "lat": -27.3167, "lon": -58.5833,
        "alerta": 6.50, "evacuacion": 7.00,
        "rio": "Paraná", "cuenca": "Paraná Medio"
    },
    "Corrientes Capital (Río Paraná)": {
        "lat": -27.4678, "lon": -58.8344,
        "alerta": 6.50, "evacuacion": 7.00,
        "rio": "Paraná", "cuenca": "Paraná Medio"
    },
    "Bella Vista (Río Paraná)": {
        "lat": -28.5083, "lon": -59.0417,
        "alerta": 5.50, "evacuacion": 6.00,
        "rio": "Paraná", "cuenca": "Paraná Medio"
    },
    "Goya (Río Paraná)": {
        "lat": -29.1442, "lon": -59.2639,
        "alerta": 5.20, "evacuacion": 5.70,
        "rio": "Paraná", "cuenca": "Baja Cuenca Paraná"
    },
    "Esquina (Río Corriente/Paraná)": {
        "lat": -30.0167, "lon": -59.5333,
        "alerta": 4.50, "evacuacion": 5.00,
        "rio": "Paraná/Corriente", "cuenca": "Baja Cuenca Paraná"
    },
    "Santo Tomé (Río Uruguay)": {
        "lat": -28.5500, "lon": -56.0333,
        "alerta": 11.50, "evacuacion": 12.50,
        "rio": "Uruguay", "cuenca": "Alto Uruguay"
    },
    "Alvear (Río Uruguay)": {
        "lat": -29.0967, "lon": -56.5483,
        "alerta": 8.50, "evacuacion": 9.50,
        "rio": "Uruguay", "cuenca": "Uruguay Medio"
    },
    "Paso de los Libres (Río Uruguay)": {
        "lat": -29.7167, "lon": -57.0833,
        "alerta": 7.50, "evacuacion": 8.50,
        "rio": "Uruguay", "cuenca": "Uruguay Medio"
    },
    "Monte Caseros (Río Uruguay)": {
        "lat": -30.2500, "lon": -57.6500,
        "alerta": 7.50, "evacuacion": 8.50,
        "rio": "Uruguay", "cuenca": "Bajo Uruguay"
    }
}

# Coordenadas centrales de Corrientes para el mapa
MAP_CENTER_CORRIENTES = [-28.5, -57.8]
