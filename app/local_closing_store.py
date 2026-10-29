"""Meses de cierre almacenados en MySQL desde v0.82.0."""

from __future__ import annotations

from datetime import date
from app.mysql_store import conectar as _conectar


def _texto_mes(valor: date) -> str:
    return date(valor.year, valor.month, 1).isoformat()


def _fecha_mes(valor: str | None) -> date | None:
    if not valor:
        return None
    if isinstance(valor, date):
        return date(valor.year, valor.month, 1)
    try:
        fecha = date.fromisoformat(valor)
    except (TypeError, ValueError):
        return None
    return date(fecha.year, fecha.month, 1)


def inicializar_cierres_local() -> None:
    """El esquema se instala explícitamente con sql/migracion_v82.sql."""


def guardar_mes_inventario(inventario_id: int, mes_cierre: date) -> None:
    with _conectar() as conexion:
        conexion.execute(
            """
            INSERT INTO inventario_cierres (inventario_id, mes_cierre)
            VALUES (?, ?)
            ON CONFLICT(inventario_id) DO UPDATE SET
                mes_cierre = excluded.mes_cierre
            """,
            (inventario_id, _texto_mes(mes_cierre)),
        )


def obtener_mes_inventario(inventario_id: int) -> date | None:
    with _conectar() as conexion:
        fila = conexion.execute(
            "SELECT mes_cierre FROM inventario_cierres WHERE inventario_id = ?",
            (inventario_id,),
        ).fetchone()
    return _fecha_mes(fila["mes_cierre"]) if fila else None


def eliminar_mes_inventario(inventario_id: int) -> None:
    with _conectar() as conexion:
        conexion.execute(
            "DELETE FROM inventario_programaciones WHERE inventario_id = ?",
            (inventario_id,),
        )
        conexion.execute(
            "DELETE FROM inventario_cierres WHERE inventario_id = ?",
            (inventario_id,),
        )


def guardar_mes_programacion(programacion_id: int, mes_cierre: date) -> None:
    with _conectar() as conexion:
        conexion.execute(
            """
            INSERT INTO programacion_cierres (
                programacion_id, mes_cierre_proximo
            ) VALUES (?, ?)
            ON CONFLICT(programacion_id) DO UPDATE SET
                mes_cierre_proximo = excluded.mes_cierre_proximo
            """,
            (programacion_id, _texto_mes(mes_cierre)),
        )


def obtener_mes_programacion(programacion_id: int) -> date | None:
    with _conectar() as conexion:
        fila = conexion.execute(
            """
            SELECT mes_cierre_proximo FROM programacion_cierres
            WHERE programacion_id = ?
            """,
            (programacion_id,),
        ).fetchone()
    return _fecha_mes(fila["mes_cierre_proximo"]) if fila else None


def eliminar_mes_programacion(programacion_id: int) -> None:
    with _conectar() as conexion:
        conexion.execute(
            "DELETE FROM inventario_programaciones WHERE programacion_id = ?",
            (programacion_id,),
        )
        conexion.execute(
            "DELETE FROM programacion_cierres WHERE programacion_id = ?",
            (programacion_id,),
        )


def existe_cierre_programacion(
    programacion_id: int,
    mes_cierre: date,
) -> bool:
    with _conectar() as conexion:
        fila = conexion.execute(
            """
            SELECT 1
            FROM inventario_cierres c
            JOIN inventario_programaciones p
              ON p.inventario_id = c.inventario_id
            WHERE p.programacion_id = ? AND c.mes_cierre = ?
            LIMIT 1
            """,
            (programacion_id, _texto_mes(mes_cierre)),
        ).fetchone()
    return fila is not None


def vincular_inventario_programacion(
    inventario_id: int,
    programacion_id: int,
) -> None:
    with _conectar() as conexion:
        conexion.execute(
            """
            INSERT INTO inventario_programaciones (inventario_id, programacion_id)
            VALUES (?, ?)
            ON CONFLICT(inventario_id) DO UPDATE SET
                programacion_id = excluded.programacion_id
            """,
            (inventario_id, programacion_id),
        )


def sincronizar_cierres_local(db) -> None:
    """Completa sólo IDs aún ausentes usando los datos actuales de MySQL."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models import Inventario, ProgramacionInventario

    programaciones = db.scalars(select(ProgramacionInventario)).all()
    por_id = {item.id: item for item in programaciones}
    for programacion in programaciones:
        if obtener_mes_programacion(programacion.id) is None:
            guardar_mes_programacion(programacion.id, programacion.fecha_proxima)

    inventarios = db.scalars(
        select(Inventario).options(selectinload(Inventario.programacion))
    ).all()
    for inventario in inventarios:
        if inventario.programacion_id:
            vincular_inventario_programacion(
                inventario.id,
                inventario.programacion_id,
            )
        if obtener_mes_inventario(inventario.id) is not None:
            continue
        programacion = por_id.get(inventario.programacion_id)
        if programacion and programacion.frecuencia == "MENSUAL":
            base = inventario.fecha_programada or inventario.fecha
        else:
            base = (
                inventario.cerrado_en.date()
                if inventario.cerrado_en
                else inventario.fecha
            )
        guardar_mes_inventario(inventario.id, base)
