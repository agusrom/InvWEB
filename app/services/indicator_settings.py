from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConfiguracionSistema


DEFAULTS = {
    "tolerancia_pct": 5.0,
    "objetivo_confiabilidad_pct": 90.0,
    "alerta_cliente_pct": 85.0,
    "minimo_renglones_alerta": 3,
}

DESCRIPCIONES = {
    "tolerancia_pct": (
        "Desvío porcentual máximo para considerar correcto un renglón."
    ),
    "objetivo_confiabilidad_pct": (
        "Meta general de confiabilidad utilizada en reportes."
    ),
    "alerta_cliente_pct": (
        "Confiabilidad por debajo de la cual se genera una alerta."
    ),
    "minimo_renglones_alerta": (
        "Muestra mínima por cliente para emitir una alerta."
    ),
}

_cache = dict(DEFAULTS)


def _convertir(clave: str, valor: str | float | int) -> float | int:
    if clave == "minimo_renglones_alerta":
        return int(float(valor))
    return float(valor)


def asegurar_configuracion(db: Session) -> dict:
    existentes = {
        item.clave: item
        for item in db.scalars(
            select(ConfiguracionSistema).where(
                ConfiguracionSistema.clave.in_(list(DEFAULTS))
            )
        ).all()
    }
    hubo_cambios = False
    for clave, valor in DEFAULTS.items():
        if clave in existentes:
            continue
        db.add(
            ConfiguracionSistema(
                clave=clave,
                valor=str(valor),
                descripcion=DESCRIPCIONES[clave],
            )
        )
        hubo_cambios = True
    if hubo_cambios:
        db.commit()
    return cargar_configuracion(db)


def cargar_configuracion(db: Session) -> dict:
    valores = dict(DEFAULTS)
    for item in db.scalars(
        select(ConfiguracionSistema).where(
            ConfiguracionSistema.clave.in_(list(DEFAULTS))
        )
    ).all():
        try:
            valores[item.clave] = _convertir(item.clave, item.valor)
        except (TypeError, ValueError):
            valores[item.clave] = DEFAULTS[item.clave]
    _cache.update(valores)
    return dict(valores)


def configuracion_actual() -> dict:
    return dict(_cache)


def guardar_configuracion(db: Session, valores: dict) -> dict:
    registros = {
        item.clave: item
        for item in db.scalars(
            select(ConfiguracionSistema).where(
                ConfiguracionSistema.clave.in_(list(DEFAULTS))
            )
        ).all()
    }
    ahora = datetime.now()
    for clave, valor in valores.items():
        registro = registros.get(clave)
        if registro is None:
            registro = ConfiguracionSistema(
                clave=clave,
                valor=str(valor),
                descripcion=DESCRIPCIONES[clave],
            )
            db.add(registro)
        else:
            registro.valor = str(valor)
            registro.descripcion = DESCRIPCIONES[clave]
            registro.actualizada_en = ahora
    db.commit()
    return cargar_configuracion(db)
