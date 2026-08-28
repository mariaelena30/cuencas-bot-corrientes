"""
Backend del Portal Hidrico Corrientes.

Servicio COMPLETAMENTE SEPARADO de cuencas-bot (Chaco). Tiene su propio
repositorio, su propio deploy en Render y su propia base de datos
(Supabase). No comparte estado ni memoria en tiempo de ejecucion con
cuencas-bot - son dos backends independientes, cada uno con sus propias
localidades, barrios, tickets SOS y reportes ciudadanos.

FUENTE DE DATOS: niveles y umbrales oficiales de Prefectura Naval
Argentina, via CIM-UNL (fich.unl.edu.ar/cim/rios/parana/alturas),
verificados en vivo el 24/08/2026. El scraper actualizar_niveles.py
(el mismo que usa cuencas-bot) ya trae estos "puertos" en
niveles_rios.json, asi que este backend puede reusar ese mismo script
sin modificarlo - solo hace falta correrlo aca tambien (o copiar/leer
el mismo niveles_rios.json si en algun momento se decide compartir esa
parte puntual del pipeline).
"""

import json
import os
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Portal Hidrico Corrientes - API")

# ---------------------------------------------------------------------
# SUPABASE (persistencia real para SOS y reportes ciudadanos)
#
# IMPORTANTE: este backend usa un proyecto de Supabase PROPIO, distinto
# al de cuencas-bot (Chaco). Hay que crear un proyecto nuevo en
# supabase.com y correr el supabase_schema_corrientes.sql de este
# mismo paquete ahi (son las mismas 2 tablas: sos_tickets y
# reportes_ciudadanos, pero en una base de datos aparte).
#
# Variables de entorno a configurar en Render (Settings -> Environment)
# para ESTE servicio: SUPABASE_URL y SUPABASE_KEY (service_role, no
# anon). Sin esas variables, cae de vuelta a listas en memoria.
# ---------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En produccion, mejor restringir a tu dominio de Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------
# EXPLICACIONES EN LENGUAJE SIMPLE
# ---------------------------------------------------------------------
EXPLICACIONES = {
    "nivel_metros": (
        "Es cuanto subio el agua del rio en ese punto, medido en metros. "
        "Cuando supera el 'umbral de alerta', hay que empezar a prestar "
        "atencion; si supera el 'umbral de evacuacion', es momento de "
        "seguir las indicaciones de Defensa Civil."
    ),
    "tipo_inundacion_dominante": (
        "FLUVIAL: el rio se desborda (sube su nivel). Da tiempo de horas "
        "a dias de aviso, y se sigue con el nivel del Parana. PLUVIAL: "
        "se inunda por lluvia local que el desague no puede evacuar, "
        "sin que el rio necesariamente haya subido - es mas repentino y "
        "localizado. En Corrientes, el interior provincial ademas tiene "
        "un tercer factor: rios internos propios (Corriente, Riachuelo, "
        "Santa Lucia) que Defensa Civil senala como el mayor problema "
        "recurrente, y que hoy no tienen estacion de medicion publica."
    ),
}

# ---------------------------------------------------------------------
# CONTEXTO DE RELIEVE — investigado 26/08/2026. Explica ESTRUCTURALMENTE
# por que el pluvial es tan relevante en Corrientes: no es solo falta
# de obras, es la geografia misma de la provincia.
# ---------------------------------------------------------------------
CONTEXTO_RELIEVE = {
    "resumen": (
        "Provincia mayormente llana. Altitud media de la provincia: ~73 m "
        "sobre el nivel del mar. Punto mas alto: cerca de San Carlos, "
        "limite con Misiones, 229 m. Los Esteros del Ibera (~12.000 km2 "
        "en Corrientes) tienen una pendiente de apenas 1 por mil, lo que "
        "hace el desague de lluvia estructuralmente muy lento en gran "
        "parte del territorio. La provincia desciende en tres 'terrazas' "
        "de este a oeste, volcando sus aguas hacia la falla que hoy "
        "ocupa el rio Corrientes y la depresion del Ibera."
    ),
    "fuente": "Wikipedia (Esteros del Ibera), patrimonionatural.com, todo-argentina.net, topographic-map.com - consultados 26/08/2026",
}

# ---------------------------------------------------------------------
# CUENCAS — Corrientes esta enteramente sobre el Rio Parana
# ---------------------------------------------------------------------
CUENCAS: dict = {
    "parana": {
        "nombre": "Rio Parana",
        "estacion": "Corrientes (capital)",
        "nivel_metros": 2.88,
        "umbral_alerta": 6.50,
        "umbral_evacuacion": 7.00,
        "fuente": "Prefectura Naval Argentina (via CIM-UNL)",
        "conectado": False,
        "ultima_verificacion": "2026-08-25",
        "tipo": "fluvial",
        "internacional": True,
        "paises_cuenca_alta": ["Brasil", "Paraguay", "Bolivia"],
    },
    # -----------------------------------------------------------------
    # CUENCAS INTERNAS DE LA PROVINCIA — sumadas 26/08/2026. Distintas
    # del Parana: no dependen del nivel del rio grande, sino de lluvia
    # local sobre una provincia con pendiente casi nula (los Esteros
    # del Ibera tienen apenas 1 por mil de pendiente, lo que hace el
    # desague naturalmente muy lento). Segun el propio director de
    # Defensa Civil de Corrientes (Bruno Lovison, declaraciones a
    # RadioNord, julio 2026), estos rios internos "suelen ser los que
    # mayores inconvenientes generan en el interior provincial".
    #
    # HONESTIDAD DE DATOS: a diferencia del Parana, NO encontramos una
    # estacion de medicion publica en tiempo real para estos rios (no
    # estan en la tabla de fich.unl.edu.ar ni en niveles_rios.json).
    # Por eso nivel_metros/umbral_alerta/umbral_evacuacion quedan en
    # None en vez de inventar un numero - falta gestionar el dato con
    # el ICAA (Instituto Correntino del Agua y del Ambiente) o Defensa
    # Civil provincial para poder monitorearlos de verdad.
    # -----------------------------------------------------------------
    "rio_corrientes": {
        "nombre": "Rio Corrientes (interno)",
        "estacion": None,
        "nivel_metros": None,
        "umbral_alerta": None,
        "umbral_evacuacion": None,
        "fuente": "Sin estacion de medicion publica conocida. Mencionado por Defensa Civil Corrientes como fuente recurrente de inundacion en el interior provincial (RadioNord, jul. 2026)",
        "conectado": False,
        "ultima_verificacion": None,
        "tipo": "pluvial_fluvial_interno",
        "internacional": False,
    },
    "riachuelo": {
        "nombre": "Riachuelo (interno)",
        "estacion": None,
        "nivel_metros": None,
        "umbral_alerta": None,
        "umbral_evacuacion": None,
        "fuente": "Sin estacion de medicion publica conocida. Mencionado por Defensa Civil Corrientes como fuente recurrente de inundacion en el interior provincial (RadioNord, jul. 2026)",
        "conectado": False,
        "ultima_verificacion": None,
        "tipo": "pluvial_fluvial_interno",
        "internacional": False,
    },
    "santa_lucia_interno": {
        "nombre": "Rio Santa Lucia (interno)",
        "estacion": None,
        "nivel_metros": None,
        "umbral_alerta": None,
        "umbral_evacuacion": None,
        "fuente": "Sin estacion de medicion publica conocida. Mencionado por Defensa Civil Corrientes como fuente recurrente de inundacion en el interior provincial (RadioNord, jul. 2026)",
        "conectado": False,
        "ultima_verificacion": None,
        "tipo": "pluvial_fluvial_interno",
        "internacional": False,
    },
}

# ---------------------------------------------------------------------
# LOCALIDADES — niveles y umbrales oficiales, RE-VERIFICADOS EN VIVO
# el 25/08/2026 contra fich.unl.edu.ar/cim/rios/parana/alturas.
# Los umbrales de alerta/evacuacion NO cambiaron respecto a la
# verificacion del 24/08 (son estables, no varian dia a dia). Los
# niveles actuales si se actualizaron a la lectura de hoy.
#
# CLAVE PARA QUE /historico FUNCIONE CON DATOS REALES: el endpoint
# compara el parametro contra el campo "puerto" tal cual lo guarda
# actualizar_niveles.py en niveles_rios.json, que a su vez copia el
# nombre EXACTO de la columna "Puerto" de la tabla de Prefectura Naval.
# La comparacion es case-insensitive pero NO ignora tildes, asi que
# hay que llamar al endpoint con el nombre EXACTO de la tabla:
#   corrientes          -> /historico/Corrientes
#   empedrado           -> /historico/Empedrado
#   bella_vista_ctes     -> /historico/Bella Vista
#   goya                -> /historico/Goya
#   ituzaingo           -> /historico/Ituzaingó   (CON tilde en la tabla)
#   itati               -> /historico/Itati       (SIN tilde en la tabla)
#   paso_de_la_patria   -> /historico/Paso de la Patria
#   ita_ibate           -> /historico/Ita Ibate    (SIN tilde en la tabla)
#   santa_ana_ctes       -> /historico/Santa Ana
# ---------------------------------------------------------------------
localidades: dict = {
    "corrientes": {
        "nombre": "Corrientes (capital)", "cuenca_clave": "parana", "nivel_metros": 2.88,
        "umbral_alerta": 6.50, "umbral_evacuacion": 7.00, "precipitacion_acumulada_mm": None,
        "fuente": "Prefectura Naval Argentina, estacion Corrientes (via CIM-UNL, verificado 25/08/2026)",
        "conectado": False, "ultima_verificacion": "2026-08-25",
        "tipo_inundacion_dominante": "fluvial",
        "influencia_internacional": "Lluvias en el centro-este de Brasil (cuenca alta del Parana) y aporte del rio Paraguay (Paraguay/Bolivia). Represa Yacyreta aguas arriba (Argentina-Paraguay).",
    },
    "empedrado": {
        "nombre": "Empedrado", "cuenca_clave": "parana", "nivel_metros": 2.95,
        "umbral_alerta": 6.50, "umbral_evacuacion": 6.70, "precipitacion_acumulada_mm": None,
        "fuente": "Prefectura Naval Argentina, estacion Empedrado (via CIM-UNL, verificado 25/08/2026)",
        "conectado": False, "ultima_verificacion": "2026-08-25",
        "tipo_inundacion_dominante": "fluvial",
        "influencia_internacional": "Lluvias en el centro-este de Brasil (cuenca alta del Parana) y aporte del rio Paraguay (Paraguay/Bolivia).",
    },
    "bella_vista_ctes": {
        "nombre": "Bella Vista", "cuenca_clave": "parana", "nivel_metros": 3.20,
        "umbral_alerta": 6.00, "umbral_evacuacion": 6.40, "precipitacion_acumulada_mm": None,
        "fuente": "Prefectura Naval Argentina, estacion Bella Vista (via CIM-UNL, verificado 25/08/2026)",
        "conectado": False, "ultima_verificacion": "2026-08-25",
        "tipo_inundacion_dominante": "fluvial",
        "influencia_internacional": "Lluvias en el centro-este de Brasil (cuenca alta del Parana) y aporte del rio Paraguay (Paraguay/Bolivia).",
    },
    "goya": {
        "nombre": "Goya", "cuenca_clave": "parana", "nivel_metros": 3.16,
        "umbral_alerta": 5.20, "umbral_evacuacion": 5.70, "precipitacion_acumulada_mm": None,
        "fuente": "Prefectura Naval Argentina, estacion Goya (via CIM-UNL, verificado 25/08/2026)",
        "conectado": False, "ultima_verificacion": "2026-08-25",
        "tipo_inundacion_dominante": "fluvial",
        "influencia_internacional": "Lluvias en el centro-este de Brasil (cuenca alta del Parana) y aporte del rio Paraguay (Paraguay/Bolivia).",
    },
    "ituzaingo": {
        "nombre": "Ituzaingó", "cuenca_clave": "parana", "nivel_metros": 1.50,
        "umbral_alerta": 3.50, "umbral_evacuacion": 4.00, "precipitacion_acumulada_mm": None,
        "fuente": "Prefectura Naval Argentina, estacion Ituzaingo (via CIM-UNL, verificado 25/08/2026)",
        "conectado": False, "ultima_verificacion": "2026-08-25",
        "tipo_inundacion_dominante": "fluvial",
        "influencia_internacional": "Influencia DIRECTA de la represa Yacyreta (Argentina-Paraguay, EBY), ademas de lluvias en el sur de Brasil sobre la cuenca alta del Parana.",
    },
    "itati": {
        "nombre": "Itatí", "cuenca_clave": "parana", "nivel_metros": 2.99,
        "umbral_alerta": 6.80, "umbral_evacuacion": 7.50, "precipitacion_acumulada_mm": None,
        "fuente": "Prefectura Naval Argentina, estacion Itati (via CIM-UNL, verificado 25/08/2026)",
        "conectado": False, "ultima_verificacion": "2026-08-25",
        "tipo_inundacion_dominante": "fluvial",
        "influencia_internacional": "Influencia directa de la operacion de la represa Yacyreta (aguas abajo inmediato) y de lluvias en el sur de Brasil.",
    },
    "paso_de_la_patria": {
        "nombre": "Paso de la Patria", "cuenca_clave": "parana", "nivel_metros": 2.93,
        "umbral_alerta": 6.50, "umbral_evacuacion": 7.00, "precipitacion_acumulada_mm": None,
        "fuente": "Prefectura Naval Argentina, estacion Paso de la Patria (via CIM-UNL, verificado 25/08/2026)",
        "conectado": False, "ultima_verificacion": "2026-08-25",
        "tipo_inundacion_dominante": "fluvial",
        "influencia_internacional": "Lluvias en el centro-este de Brasil (cuenca alta del Parana) y aporte del rio Paraguay (Paraguay/Bolivia).",
    },
    "ita_ibate": {
        "nombre": "Ita Ibaté", "cuenca_clave": "parana", "nivel_metros": 1.86,
        "umbral_alerta": 7.00, "umbral_evacuacion": 7.50, "precipitacion_acumulada_mm": None,
        "fuente": "Prefectura Naval Argentina, estacion Ita Ibate (via CIM-UNL, verificado 25/08/2026)",
        "conectado": False, "ultima_verificacion": "2026-08-25",
        "tipo_inundacion_dominante": "fluvial",
        "influencia_internacional": "Lluvias en el centro-este de Brasil (cuenca alta del Parana) y aporte del rio Paraguay (Paraguay/Bolivia).",
    },
    "santa_ana_ctes": {
        "nombre": "Santa Ana", "cuenca_clave": "parana", "nivel_metros": 7.47,
        "umbral_alerta": 9.30, "umbral_evacuacion": 9.80, "precipitacion_acumulada_mm": None,
        "fuente": "Prefectura Naval Argentina, estacion Santa Ana (via CIM-UNL, verificado 25/08/2026)",
        "conectado": False, "ultima_verificacion": "2026-08-25",
        "tipo_inundacion_dominante": "fluvial",
        "influencia_internacional": "Lluvias en el sur de Brasil sobre la cuenca alta del rio Parana.",
    },
}

# ---------------------------------------------------------------------
# BARRIOS VULNERABLES — solo Corrientes capital por ahora. Reportados
# por prensa como zonas anegadas en la crecida de dic. 2025 / ene. 2026.
# NO se inventan coordenadas propias ni conteo de familias: falta un
# dato oficial de Defensa Civil / Municipalidad de Corrientes para
# completar esto con precision, asi que esos campos quedan en None.
# ---------------------------------------------------------------------
BARRIOS_VULNERABLES: dict = {
    "la_olla_ctes": {
        "nombre": "Barrio La Olla", "localidad_padre": "corrientes",
        "lat": -27.4692, "lon": -58.8306,
        "precision": "aproximada (coordenadas del centro de Corrientes capital, sin geolocalizacion propia verificada)",
        "motivo": "Reportado en prensa como una de las zonas mas afectadas por anegamiento en la crecida de dic. 2025 / ene. 2026",
        "cota_inundacion_m": None, "familias_estimadas": None,
        "via_acceso_critica": "Sin dato verificado",
        "tipo_inundacion_dominante": "pluvial (hipotesis, sin confirmar por Defensa Civil): la provincia tiene pendiente casi nula (los Esteros del Ibera bajan apenas 1 por mil), por lo que el desague de lluvia local es estructuralmente lento en toda la zona baja de la capital, independiente del nivel del Parana.",
    },
    "san_ignacio_ctes": {
        "nombre": "Barrio San Ignacio", "localidad_padre": "corrientes",
        "lat": -27.4692, "lon": -58.8306,
        "precision": "aproximada (coordenadas del centro de Corrientes capital, sin geolocalizacion propia verificada)",
        "motivo": "Reportado en prensa como zona anegada en la crecida de dic. 2025 / ene. 2026",
        "cota_inundacion_m": None, "familias_estimadas": None,
        "via_acceso_critica": "Sin dato verificado",
        "tipo_inundacion_dominante": "pluvial (hipotesis, sin confirmar por Defensa Civil): la provincia tiene pendiente casi nula (los Esteros del Ibera bajan apenas 1 por mil), por lo que el desague de lluvia local es estructuralmente lento en toda la zona baja de la capital, independiente del nivel del Parana.",
    },
    "laguna_seca_ctes": {
        "nombre": "Laguna Seca", "localidad_padre": "corrientes",
        "lat": -27.4692, "lon": -58.8306,
        "precision": "aproximada (coordenadas del centro de Corrientes capital, sin geolocalizacion propia verificada)",
        "motivo": "Reportado en prensa como zona anegada, con escuela usada como referencia de evacuacion en la crecida de dic. 2025 / ene. 2026",
        "cota_inundacion_m": None, "familias_estimadas": None,
        "via_acceso_critica": "Sin dato verificado",
        "tipo_inundacion_dominante": "pluvial (hipotesis, sin confirmar por Defensa Civil): la provincia tiene pendiente casi nula (los Esteros del Ibera bajan apenas 1 por mil), por lo que el desague de lluvia local es estructuralmente lento en toda la zona baja de la capital, independiente del nivel del Parana.",
    },
    "anahi_ctes": {
        "nombre": "Barrio Anahí", "localidad_padre": "corrientes",
        "lat": -27.4692, "lon": -58.8306,
        "precision": "aproximada (coordenadas del centro de Corrientes capital, sin geolocalizacion propia verificada)",
        "motivo": "Reportado en prensa como zona anegada en la crecida de dic. 2025 / ene. 2026",
        "cota_inundacion_m": None, "familias_estimadas": None,
        "via_acceso_critica": "Sin dato verificado",
        "tipo_inundacion_dominante": "pluvial (hipotesis, sin confirmar por Defensa Civil): la provincia tiene pendiente casi nula (los Esteros del Ibera bajan apenas 1 por mil), por lo que el desague de lluvia local es estructuralmente lento en toda la zona baja de la capital, independiente del nivel del Parana.",
    },
}


# ---------------------------------------------------------------------
# CLASIFICACION DE ESTADO (verde/amarillo/rojo)
# ---------------------------------------------------------------------
def calcular_estado(nivel, umbral_alerta, umbral_evacuacion):
    if nivel is None or umbral_alerta is None or umbral_evacuacion is None:
        return "SIN_DATO", "⚪"
    if nivel >= umbral_evacuacion:
        return "EVACUACION", "🔴"
    if nivel >= umbral_alerta:
        return "ALERTA", "🟡"
    return "NORMAL", "🟢"


def _cuenca_con_estado(clave: str) -> dict:
    c = CUENCAS[clave]
    estado, emoji = calcular_estado(c["nivel_metros"], c["umbral_alerta"], c["umbral_evacuacion"])
    return {**c, "clave": clave, "estado": estado, "emoji": emoji}


def _localidad_con_estado(clave: str) -> dict:
    loc = localidades[clave]
    estado, emoji = calcular_estado(loc["nivel_metros"], loc["umbral_alerta"], loc["umbral_evacuacion"])
    return {**loc, "clave": clave, "estado": estado, "emoji": emoji}


class ActualizacionHidrologia(BaseModel):
    localidad: str
    nivel_metros: float
    precipitacion_acumulada_mm: float | None = None


# ---------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------
@app.get("/historico/{estacion}")
def obtener_historico(estacion: str, dias: int = 60):
    """
    Serie historica de niveles para una estacion de niveles_rios.json
    (ej. "Corrientes", "Empedrado", "Goya"). Necesita que este servicio
    corra su propia copia de actualizar_niveles.py (o lea el mismo
    niveles_rios.json que genera cuencas-bot, si se decide compartir
    solo ese archivo puntual).
    """
    try:
        with open("niveles_rios.json", "r", encoding="utf-8") as fh:
            historico = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"estacion": estacion, "lecturas": [], "error": "Historico no disponible todavia."}

    limite = datetime.now(timezone.utc) - timedelta(days=dias)

    def _fecha(fila):
        try:
            f = datetime.fromisoformat(fila["timestamp_consulta"].replace("Z", "+00:00"))
            return f if f.tzinfo else f.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError, TypeError):
            return None

    lecturas = []
    for fila in historico:
        if fila.get("puerto", "").strip().lower() != estacion.strip().lower():
            continue
        fecha = _fecha(fila)
        if fecha is None or fecha < limite:
            continue
        lecturas.append({
            "fecha": fila["timestamp_consulta"],
            "altura_m": fila.get("altura_actual_m"),
        })

    lecturas.sort(key=lambda l: l["fecha"])
    return {"estacion": estacion, "lecturas": lecturas, "n_lecturas": len(lecturas)}


@app.get("/")
def raiz():
    return {"servicio": "Portal Hidrico Corrientes - API", "estado": "activo"}


# ---------------------------------------------------------------------
# ORGANISMOS RELEVANTES — investigado y verificado 26/08/2026. Mezcla
# de nivel nacional, provincial (Corrientes) y binacional. Los datos
# de contacto/URL son los oficiales publicos; no se inventan telefonos
# ni direcciones que no se pudieron verificar.
# ---------------------------------------------------------------------
ORGANISMOS: dict = {
    "smn": {
        "nombre": "Servicio Meteorologico Nacional (SMN)",
        "nivel": "nacional",
        "dependencia": "Ministerio de Defensa",
        "rol": "Pronostico del tiempo y sistema de alerta temprana meteorologica (3 niveles: amarillo/naranja/rojo). Tiene seccion de datos abiertos.",
        "url": "https://www.smn.gob.ar",
        "url_alertas": "https://www.smn.gob.ar/alertas",
    },
    "ina": {
        "nombre": "Instituto Nacional del Agua (INA)",
        "nivel": "nacional",
        "dependencia": "Secretaria de Infraestructura y Politica Hidrica, Ministerio de Obras Publicas",
        "rol": "Calcula los PRONOSTICOS hidrologicos (no solo mide el nivel actual) de los rios Parana, Paraguay, Iguazu y Uruguay, via su Sistema de Informacion y Alerta Hidrologico (SIyAH). Reportes diarios.",
        "url": "https://www.ina.gob.ar/siyah/index.php",
        "url_alertas": "https://alerta.ina.gob.ar/a5/diario/reporte_diario",
    },
    "icaa": {
        "nombre": "Instituto Correntino del Agua y del Ambiente (ICAA)",
        "nivel": "provincial (Corrientes)",
        "dependencia": "Gobierno de la Provincia de Corrientes",
        "rol": "Organismo hidrico PROVINCIAL de Corrientes. Redifunde y contextualiza para las localidades correntinas los informes del INA y de la Entidad Binacional Yacyreta (EBY).",
        "url": "https://icaa.corrientes.gob.ar",
    },
    "defensa_civil_corrientes": {
        "nombre": "Direccion de Defensa Civil de la Provincia de Corrientes",
        "nivel": "provincial (Corrientes)",
        "dependencia": "Gobierno de la Provincia de Corrientes",
        "rol": "Coordinacion operativa de emergencias hidricas provinciales, articulado con el Ministerio de Obras y Servicios Publicos (MOSP). Segun declaraciones publicas de su director (2026), los rios internos (Corriente, Riachuelo, Santa Lucia) son la mayor fuente de problemas en el interior provincial.",
        "url": None,
    },
    "eby": {
        "nombre": "Entidad Binacional Yacyreta (EBY)",
        "nivel": "binacional (Argentina-Paraguay)",
        "dependencia": "Gobiernos de Argentina y Paraguay",
        "rol": "Gestiona la represa Yacyreta (tramo Ituzaingo-Itati). Publica los caudales erogados, que inciden directo en esas dos localidades.",
        "url": None,
    },
    "sinagir": {
        "nombre": "Sistema Nacional de Gestion Integral del Riesgo (SINAGIR)",
        "nivel": "nacional",
        "dependencia": "Jefatura de Gabinete de Ministros (creado por Ley 27.287)",
        "rol": "Coordina en emergencias a las Fuerzas Armadas, el SMN, el Instituto Geografico Nacional y demas organismos bajo la orbita de Defensa.",
        "url": None,
    },
}


@app.get("/organismos")
def listar_organismos():
    return {"organismos": ORGANISMOS}


@app.get("/relieve")
def relieve_provincial():
    return CONTEXTO_RELIEVE


@app.get("/localidades")
def listar_localidades():
    return {
        "localidades": {clave: _localidad_con_estado(clave) for clave in localidades},
        "explicaciones": EXPLICACIONES,
    }


@app.get("/localidades/{clave}")
def obtener_localidad(clave: str):
    clave = clave.lower()
    if clave not in localidades:
        return {"error": f"Localidad '{clave}' no encontrada"}
    return {"localidad": _localidad_con_estado(clave), "explicaciones": EXPLICACIONES}


@app.get("/cuencas")
def listar_cuencas():
    return {
        "cuencas": {clave: _cuenca_con_estado(clave) for clave in CUENCAS},
        "explicaciones": EXPLICACIONES,
    }


@app.get("/cuencas/{clave}")
def obtener_cuenca(clave: str):
    clave = clave.lower()
    if clave not in CUENCAS:
        return {"error": f"Cuenca '{clave}' no encontrada"}
    localidades_de_la_cuenca = [
        _localidad_con_estado(c) for c, v in localidades.items() if v["cuenca_clave"] == clave
    ]
    return {
        "cuenca": _cuenca_con_estado(clave),
        "localidades": localidades_de_la_cuenca,
        "explicaciones": EXPLICACIONES,
    }


@app.get("/bot/consultar")
def consultar_para_bot():
    """Endpoint de compatibilidad, mismo formato que el de cuencas-bot."""
    cap = _localidad_con_estado("corrientes")
    return {
        "hidrologia": {
            "estacion": cap["nombre"],
            "nivel_metros": cap["nivel_metros"],
            "estado": cap["estado"],
            "umbral_alerta": cap["umbral_alerta"],
            "umbral_evacuacion": cap["umbral_evacuacion"],
            "fuente": cap["fuente"],
            "ultima_verificacion": cap["ultima_verificacion"],
        },
    }


@app.get("/barrios")
def listar_barrios():
    resultado = {}
    for clave, b in BARRIOS_VULNERABLES.items():
        padre = _localidad_con_estado(b["localidad_padre"])
        resultado[clave] = {
            **b, "clave": clave,
            "estado": padre["estado"], "emoji": padre["emoji"],
            "nombre_localidad_padre": padre["nombre"],
        }
    return {"barrios": resultado}


@app.get("/barrios/{localidad_clave}")
def barrios_de_localidad(localidad_clave: str):
    localidad_clave = localidad_clave.lower()
    if localidad_clave not in localidades:
        return {"error": f"Localidad '{localidad_clave}' no encontrada"}
    padre = _localidad_con_estado(localidad_clave)
    resultado = {
        clave: {**b, "clave": clave, "estado": padre["estado"], "emoji": padre["emoji"]}
        for clave, b in BARRIOS_VULNERABLES.items()
        if b["localidad_padre"] == localidad_clave
    }
    return {"barrios": resultado}


@app.post("/hidrologia/actualizar")
def actualizar_hidrologia(datos: ActualizacionHidrologia):
    clave = datos.localidad.lower()
    if clave not in localidades:
        return {"error": f"Localidad '{datos.localidad}' no reconocida"}
    localidades[clave]["nivel_metros"] = datos.nivel_metros
    if datos.precipitacion_acumulada_mm is not None:
        localidades[clave]["precipitacion_acumulada_mm"] = datos.precipitacion_acumulada_mm
    localidades[clave]["conectado"] = True
    localidades[clave]["ultima_verificacion"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return {"ok": True, "localidad": _localidad_con_estado(clave)}


# ---------------------------------------------------------------------
# SOS Y REPORTES CIUDADANOS — propios de este backend, no comparten
# tabla ni proyecto de Supabase con cuencas-bot (Chaco).
# ---------------------------------------------------------------------
tickets_sos: list = []
reportes_ciudadanos: list = []


class SolicitudSOS(BaseModel):
    nombre: str
    telefono: str
    localidad: str
    direccion: str | None = None
    lat: float
    lon: float
    personas_afectadas: int = 1
    altura_agua_cm: int | None = None
    nivel_urgencia: str = "ALTO"  # ALTO / MEDIO / BAJO
    requiere: list[str] = []
    notas: str | None = None


class ActualizacionSOS(BaseModel):
    estado: str  # PENDIENTE / DESPACHADO / RESUELTO
    unidad_asignada: str | None = None
    notas_despacho: str | None = None


class ReporteCiudadano(BaseModel):
    nombre: str
    localidad: str
    calle: str
    lat: float
    lon: float
    nivel_agua_aprox: str = "CORDON"
    descripcion: str | None = None


@app.post("/sos")
def crear_solicitud_sos(datos: SolicitudSOS):
    if datos.localidad.lower() not in localidades:
        return {"error": f"Localidad '{datos.localidad}' no reconocida"}
    ticket = {
        "id": f"sos_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        **datos.model_dump(),
        "estado": "PENDIENTE",
        "unidad_asignada": None,
        "notas_despacho": None,
    }
    if supabase:
        supabase.table("sos_tickets").insert(ticket).execute()
    else:
        tickets_sos.insert(0, ticket)
    return {"ok": True, "ticket": ticket}


@app.get("/sos")
def listar_solicitudes_sos():
    if supabase:
        resultado = (
            supabase.table("sos_tickets")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return {"tickets": resultado.data}
    return {"tickets": tickets_sos}


@app.patch("/sos/{ticket_id}")
def actualizar_solicitud_sos(ticket_id: str, datos: ActualizacionSOS):
    cambios = {"estado": datos.estado}
    if datos.unidad_asignada is not None:
        cambios["unidad_asignada"] = datos.unidad_asignada
    if datos.notas_despacho is not None:
        cambios["notas_despacho"] = datos.notas_despacho

    if supabase:
        resultado = (
            supabase.table("sos_tickets").update(cambios).eq("id", ticket_id).execute()
        )
        if not resultado.data:
            return {"error": f"Ticket '{ticket_id}' no encontrado"}
        return {"ok": True, "ticket": resultado.data[0]}

    ticket = next((t for t in tickets_sos if t["id"] == ticket_id), None)
    if ticket is None:
        return {"error": f"Ticket '{ticket_id}' no encontrado"}
    ticket.update(cambios)
    return {"ok": True, "ticket": ticket}


@app.post("/reportes")
def crear_reporte_ciudadano(datos: ReporteCiudadano):
    if datos.localidad.lower() not in localidades:
        return {"error": f"Localidad '{datos.localidad}' no reconocida"}
    reporte = {
        "id": f"rep_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        **datos.model_dump(),
    }
    if supabase:
        supabase.table("reportes_ciudadanos").insert(reporte).execute()
    else:
        reportes_ciudadanos.insert(0, reporte)
    return {"ok": True, "reporte": reporte}


@app.get("/reportes")
def listar_reportes_ciudadanos():
    if supabase:
        resultado = (
            supabase.table("reportes_ciudadanos")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return {"reportes": resultado.data}
    return {"reportes": reportes_ciudadanos}


# NOTA: todavia no hay bot.py / whatsapp_webhook.py propio para
# Corrientes. Cuando decidamos la Etapa 2 (alertas por Telegram +
# WhatsApp), se arma un bot separado que le pegue a ESTA API, igual
# que bot.py le pega a cuencas-bot para Chaco.

# ---------------------------------------------------------------------
# ETAPA 2 — ALERTA TEMPRANA (Telegram + Google/FCM + email de respaldo)
# ---------------------------------------------------------------------
from alertas import router as alertas_router, registrar_supabase, verificar_y_disparar_alertas

app.include_router(alertas_router)

if supabase:
    registrar_supabase(supabase)


@app.post("/alertas/verificar")
def verificar_alertas():
    """
    Compara el estado actual de cada localidad contra el ultimo estado
    conocido y dispara avisos (Telegram/push/email) a quien este
    suscripto, solo cuando una localidad SUBE de estado (ej. NORMAL ->
    ALERTA). Pensado para llamarse desde un cron externo (Render Cron
    Job o GitHub Actions) cada 15-30 min.
    """
    return verificar_y_disparar_alertas(localidades, calcular_estado)
