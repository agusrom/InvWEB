"""Notas de análisis de preconciliación, separadas del conteo original."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from app.config import BASE_DIR


STORE_PATH = BASE_DIR / "data" / "preconciliacion_notas.json"
_LOCK = Lock()
CONTROLES_PERMITIDOS = {
    "conteo",
    "ingresos",
    "egresos",
    "scrap",
    "ajustes",
}


def _leer() -> dict:
    if not STORE_PATH.exists():
        return {}
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def notas_inventario(inventario_id: int) -> dict[str, dict]:
    with _LOCK:
        return dict(_leer().get(str(inventario_id), {}))


def guardar_nota(
    inventario_id: int,
    codigo: str,
    causa: str,
    observacion: str,
    estado: str,
    controles: dict[str, bool] | None = None,
) -> dict:
    clave = codigo.strip().upper()
    with _LOCK:
        datos = _leer()
        inventario = datos.setdefault(str(inventario_id), {})
        inventario[clave] = {
            "causa": causa.strip(),
            "observacion": observacion.strip(),
            "estado": estado.strip() or "PENDIENTE",
            "controles": {
                nombre: bool(valor)
                for nombre, valor in (controles or {}).items()
                if nombre in CONTROLES_PERMITIDOS
            },
        }
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporal = STORE_PATH.with_suffix(".tmp")
        temporal.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporal.replace(STORE_PATH)
        return dict(inventario[clave])
