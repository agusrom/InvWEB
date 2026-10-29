from __future__ import annotations

import re
from collections.abc import Iterable


UBICACIONES_FISICAS = (
    "DISPONIBLE",
    "LINEA",
    "SCRAP",
    "SIN_UBICACION",
)

PREFIJO_UBICACION = re.compile(
    r"^\[(DISPONIBLE|LINEA|SCRAP)\]\s*",
    flags=re.IGNORECASE,
)


def ubicacion_de_registro(observacion: str | None) -> str:
    coincidencia = PREFIJO_UBICACION.match(str(observacion or "").strip())
    return coincidencia.group(1).upper() if coincidencia else "SIN_UBICACION"


def desglosar_conteo_por_ubicacion(items: Iterable, cajas: Iterable[dict]) -> dict[int, dict]:
    """Distribuye el físico de cada renglón según la ubicación de sus registros.

    La diferencia entre el físico del renglón y la suma de registros representa
    la base escrita directamente desde PC (o conteos anteriores sin ubicación).
    """
    items = list(items)
    desglose = {
        int(item.id): {ubicacion: 0.0 for ubicacion in UBICACIONES_FISICAS}
        for item in items
    }
    total_registros = {int(item.id): 0.0 for item in items}

    for caja in cajas:
        item_id = int(caja["item_id"])
        if item_id not in desglose:
            continue
        cantidad = float(caja.get("cantidad") or 0)
        ubicacion = ubicacion_de_registro(caja.get("observacion"))
        desglose[item_id][ubicacion] += cantidad
        total_registros[item_id] += cantidad

    for item in items:
        item_id = int(item.id)
        if item.conteo_fisico is None:
            desglose[item_id] = {
                ubicacion: None for ubicacion in UBICACIONES_FISICAS
            }
            continue
        base_sin_ubicacion = float(item.conteo_fisico) - total_registros[item_id]
        desglose[item_id]["SIN_UBICACION"] += base_sin_ubicacion
        for ubicacion, cantidad in desglose[item_id].items():
            if abs(cantidad) < 1e-9:
                desglose[item_id][ubicacion] = 0.0

    return desglose
