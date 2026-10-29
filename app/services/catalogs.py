import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Persona, Sector, TipoInventario


TIPOS_PREDETERMINADOS = (
    {
        "codigo": "PIEZAS_PROCESO",
        "nombre": "Piezas y proceso",
        "descripcion": "Conteo estándar de material, proceso y terminado.",
        "motor": "PIEZAS",
        "modalidad": "ESTANDAR",
        "formato_impresion": "FLUJO_HORIZONTAL",
        "orden": 10,
    },
    {
        "codigo": "MEDIOS",
        "nombre": "Medios",
        "descripcion": "Conteo de medios vacíos, llenos y rotos.",
        "motor": "PIEZAS",
        "modalidad": "MEDIOS",
        "formato_impresion": "MEDIOS",
        "orden": 20,
    },
    {
        "codigo": "MATERIA_PRIMA",
        "nombre": "Materia prima",
        "descripcion": "Conteo de materiales y lotes.",
        "motor": "MATERIA_PRIMA",
        "modalidad": "ESTANDAR",
        "formato_impresion": "MATERIA_PRIMA",
        "orden": 30,
    },
    {
        "codigo": "CICLICO",
        "nombre": "Cíclico",
        "descripcion": "Explosión desde una pieza raíz.",
        "motor": "CICLICO",
        "modalidad": "ESTANDAR",
        "formato_impresion": "CICLICO",
        "orden": 40,
    },
)


def codigo_catalogo(nombre: str, limite: int = 50) -> str:
    texto = unicodedata.normalize("NFKD", nombre)
    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )
    return re.sub(r"[^A-Z0-9]+", "_", texto.upper()).strip("_")[:limite]


def asegurar_catalogos(db: Session) -> None:
    for datos in TIPOS_PREDETERMINADOS:
        tipo = db.get(TipoInventario, datos["codigo"])
        if tipo is None:
            db.add(TipoInventario(**datos))

    if db.scalar(select(Sector.id).limit(1)) is None:
        logistica = Sector(
            nombre="Logística",
            descripcion="Logística, inventarios y abastecimiento.",
            orden=10,
        )
        db.add(logistica)
        db.flush()
        db.add(
            Persona(
                nombre="Agustín Romero",
                sector_id=logistica.id,
                orden=10,
            )
        )
    db.commit()


def tipo_dict(tipo: TipoInventario) -> dict:
    return {
        "codigo": tipo.codigo,
        "nombre": tipo.nombre,
        "descripcion": tipo.descripcion,
        "motor": tipo.motor,
        "modalidad": tipo.modalidad,
        "formato_impresion": tipo.formato_impresion,
        "orden": tipo.orden,
        "activo": tipo.activo,
    }


def sector_dict(sector: Sector) -> dict:
    return {
        "id": sector.id,
        "nombre": sector.nombre,
        "descripcion": sector.descripcion,
        "orden": sector.orden,
        "activo": sector.activo,
        "personas": len(sector.personas),
    }


def persona_dict(persona: Persona) -> dict:
    return {
        "id": persona.id,
        "nombre": persona.nombre,
        "sector_id": persona.sector_id,
        "sector": persona.sector.nombre if persona.sector else "",
        "legajo": persona.legajo,
        "contacto": persona.contacto,
        "orden": persona.orden,
        "activo": persona.activo,
    }
