"""Lectura auditable de ajustes de stock registrados en ``produc16``."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import bindparam, text

from app.database import production_engine
from app.services.piece_provider import normalizar_codigo


def _fecha(valor: date | datetime | str) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor).strip()[:10])


def _fecha_texto(valor: Any) -> str:
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor or "").strip()[:10]


def _operacion(valor: Any) -> str:
    texto = str(valor or "").strip()
    if texto.endswith(".0") and texto[:-2].isdigit():
        texto = texto[:-2]
    return texto


def obtener_ajustes_sistema(
    codigos: set[str],
    fecha_inicial: date | datetime | str,
    fecha_final: date | datetime | str,
) -> dict[str, list[dict]]:
    """Devuelve ajustes por pieza dentro de ``inicial < fecha <= final``.

    ``OPE1_ = 999`` identifica producto terminado. Las demás operaciones se
    presentan como proceso. Los ajustes son evidencia del sistema: no se suman
    a la evolución física de la conciliación.
    """
    codigos_normalizados = sorted({
        normalizar_codigo(codigo) for codigo in codigos
        if normalizar_codigo(codigo)
    })
    if production_engine is None or not codigos_normalizados:
        return {}

    inicial = _fecha(fecha_inicial)
    final = _fecha(fecha_final)
    consulta = text(
        """
        SELECT
            TRIM(`GCOD_`) AS codigo,
            TRIM(CAST(`OPE1_` AS CHAR)) AS operacion,
            COALESCE(`CANT_`, 0) AS cantidad,
            `FECH_` AS fecha,
            TRIM(COALESCE(`MOTI_`, '')) AS motivo
        FROM `produc16`
        WHERE `FECH_` >= :fecha_desde
          AND `FECH_` < :fecha_hasta
          AND UPPER(TRIM(`GCOD_`)) IN :codigos
        ORDER BY `FECH_`, TRIM(`GCOD_`), TRIM(CAST(`OPE1_` AS CHAR))
        """
    ).bindparams(bindparam("codigos", expanding=True))
    with production_engine.connect() as conexion:
        filas = conexion.execute(
            consulta,
            {
                "fecha_desde": inicial + timedelta(days=1),
                "fecha_hasta": final + timedelta(days=1),
                "codigos": codigos_normalizados,
            },
        ).mappings().all()

    resultado: dict[str, list[dict]] = {}
    for fila in filas:
        codigo = normalizar_codigo(fila["codigo"])
        operacion = _operacion(fila["operacion"])
        cantidad = float(fila["cantidad"] or 0)
        resultado.setdefault(codigo, []).append({
            "codigo": codigo,
            "operacion": operacion,
            "etapa": "TERMINADO" if operacion == "999" else "PROCESO",
            "cantidad": cantidad,
            "fecha": _fecha_texto(fila["fecha"]),
            "motivo": str(fila["motivo"] or "").strip(),
        })
    return resultado


def resumen_ajustes(ajustes: list[dict]) -> dict:
    """Resume cantidad neta y magnitud sin perder el detalle original."""
    terminado = sum(
        float(item.get("cantidad", 0))
        for item in ajustes if item.get("etapa") == "TERMINADO"
    )
    proceso = sum(
        float(item.get("cantidad", 0))
        for item in ajustes if item.get("etapa") != "TERMINADO"
    )
    return {
        "cantidad": len(ajustes),
        "neto": terminado + proceso,
        "magnitud": sum(abs(float(item.get("cantidad", 0))) for item in ajustes),
        "producto_terminado": terminado,
        "en_proceso": proceso,
    }
