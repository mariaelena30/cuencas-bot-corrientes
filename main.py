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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- 1. IMPORTAMOS EL ROUTER SATELITAL AISLADO ---
from satelites_ctes import router as satelites_router

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

# --- 2. INCLUIMOS EL ROUTER SATELITAL CON SUS ENDPOINTS EN FASTAPI ---
app.include_router(satelites_router)

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

# Modelos de Datos Pydantic para el Portal de Corrientes
class SOSTicket(BaseModel):
    barrio: str
    localidad: str
    telefono: str
    descripcion: str

class ReporteCiudadano(BaseModel):
    barrio: str
    localidad: str
    categoria: str
    descripcion: str

memory_sos_tickets = []
memory_reportes = []

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Portal Hídrico Corrientes",
        "modulo_satelital": "Conectado via satelites_ctes.py",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/api/sos")
def crear_ticket_sos(ticket: SOSTicket):
    if supabase:
        response = supabase.table("sos_tickets").insert(ticket.model_dump()).execute()
        return {"status": "success", "data": response.data}
    else:
        ticket_dict = ticket.model_dump()
        memory_sos_tickets.append(ticket_dict)
        return {"status": "success", "data": ticket_dict, "storage": "memory"}

@app.post("/api/reportes")
def crear_reporte_ciudadano(reporte: ReporteCiudadano):
    if supabase:
        response = supabase.table("reportes_ciudadanos").insert(reporte.model_dump()).execute()
        return {"status": "success", "data": response.data}
    else:
        reporte_dict = reporte.model_dump()
        memory_reportes.append(reporte_dict)
        return {"status": "success", "data": reporte_dict, "storage": "memory"}

@app.get("/api/niveles")
def obtener_niveles_corrientes():
    ruta_json = "niveles_rios.json"
    if not os.path.exists(ruta_json):
        raise HTTPException(status_code=404, detail="Archivo de niveles hídricos no disponible.")
        
    with open(ruta_json, "r", encoding="utf-8") as f:
        datos = json.load(f)
    
    puertos_corrientes = ["Corrientes", "Itatí", "Paso de la Patria", "Bella Vista", "Goya", "Esquina"]
    niveles_filtrados = {p: datos.get(p, {"nivel": "N/D", "estado": "Sin datos"}) for p in puertos_corrientes}
    
    return {
        "fuente": "Prefectura Naval Argentina vía CIM-UNL",
        "puertos": niveles_filtrados,
        "contexto_geografico": CONTEXTO_RELIEVE
    }
