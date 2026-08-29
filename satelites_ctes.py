import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException

# Usamos APIRouter para empaquetar los endpoints satelitales de forma independiente
router = APIRouter(prefix="/api/satelite", tags=["Satelital (CONAE Style)"])

GEE_PROJECT = os.environ.get("GEE_PROJECT")
ee_disponible = False

# Inicialización aislada de Earth Engine
try:
    import ee
    if GEE_PROJECT:
        ee.Initialize(project=GEE_PROJECT)
        ee_disponible = True
        print("CONAE MODO ACTIVE: Conexión con infraestructura satelital establecida en satelites_ctes.py.")
    else:
        print("ADVERTENCIA SATELITAL: Falta la variable GEE_PROJECT en las variables de entorno.")
except Exception as e:
    print(f"ERROR SATELITAL: No se pudo conectar con Earth Engine: {e}")


@router.get("/agua")
def obtener_capa_satelital_agua():
    """
    Procesa imágenes de Sentinel-2 en tiempo real y devuelve las coordenadas de tiles
    para renderizar en mapas web interactivos (Leaflet/Mapbox).
    """
    if not ee_disponible:
        raise HTTPException(
            status_code=503, 
            detail="Servicio satelital desactivado. Verifique la variable de entorno GEE_PROJECT."
        )
    
    try:
        # Delimitar área de la provincia de Corrientes
        corrientes_bbox = ee.Geometry.Rectangle([-59.7, -30.7, -55.6, -27.2])
        
        # Ventana temporal de búsqueda (últimos 15 días)
        fecha_fin = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        fecha_inicio = (datetime.now(timezone.utc) - timedelta(days=15)).strftime('%Y-%m-%d')
        
        # Traer imágenes satelitales de la Agencia Espacial Europea libres de nubes
        coleccion = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(corrientes_bbox)
                     .filterDate(fecha_inicio, fecha_fin)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 12)))
        
        if coleccion.size().getInfo() == 0:
            raise HTTPException(status_code=404, detail="No se hallaron capturas satelitales limpias recientes.")
        
        # Mosaico y cálculo científico del índice hídrico (NDWI)
        imagen_compuesta = coleccion.median().clip(corrientes_bbox)
        ndwi = imagen_compuesta.normalizedDifference(['B3', 'B8']) # Bandas Verde e Infrarroja (NIR)
        
        # Máscara binaria: Valores mayores a 0 significan agua líquida en superficie
        capa_agua = ndwi.gt(0.0).selfMask()
        
        # Generar mapa de teselas (Tiles) para el Frontend
        map_id = capa_agua.getMapId({
            'min': 0,
            'max': 1,
            'palette': ['1A73E8'] # Azul eléctrico institucional
        })
        
        return {
            "estado": "success",
            "metadatos": {
                "satelite": "Sentinel-2 L2A (Óptico/Infrarrojo)",
                "procesamiento": "Índice NDWI de Masa de Agua Superficial",
                "rango_analizado": f"{fecha_inicio} al {fecha_fin}"
            },
            "tile_url": map_id['tile_fetcher'].url_format
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fallo en procesamiento geoespacial: {str(e)}")
