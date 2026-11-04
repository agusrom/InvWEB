"""Relaciones MySQL entre inventarios originales y reconteos."""

from __future__ import annotations

from datetime import datetime
from app.mysql_store import conectar as _conexion


def inicializar_reconteos_local() -> None:
    """El esquema se instala explícitamente con sql/migracion_v82.sql."""


def crear_relacion(inventario_origen_id: int, inventario_reconteo_id: int,
                   tipo: str, stock_referencia: str) -> dict:
    with _conexion() as conexion:
        numero = conexion.execute(
            "SELECT COALESCE(MAX(numero_reconteo), 0) + 1 "
            "FROM inventarios_relaciones WHERE inventario_origen_id = ?",
            (inventario_origen_id,),
        ).fetchone()[0]
        cursor = conexion.execute("""
            INSERT INTO inventarios_relaciones
                (inventario_origen_id, inventario_reconteo_id, numero_reconteo,
                 tipo, stock_referencia, creado_en)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            inventario_origen_id, inventario_reconteo_id, numero, tipo,
            stock_referencia, datetime.now().isoformat(timespec="seconds"),
        ))
        fila = conexion.execute(
            "SELECT * FROM inventarios_relaciones WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(fila)


def relaciones_de_inventario(inventario_id: int) -> dict:
    with _conexion() as conexion:
        origen = conexion.execute(
            "SELECT * FROM inventarios_relaciones "
            "WHERE inventario_reconteo_id = ?",
            (inventario_id,),
        ).fetchone()
        hijos = conexion.execute(
            "SELECT * FROM inventarios_relaciones "
            "WHERE inventario_origen_id = ? ORDER BY numero_reconteo",
            (inventario_id,),
        ).fetchall()
    return {
        "origen": dict(origen) if origen else None,
        "reconteos": [dict(fila) for fila in hijos],
    }


def eliminar_relaciones_inventario(inventario_id: int) -> None:
    with _conexion() as conexion:
        conexion.execute(
            "DELETE FROM inventarios_relaciones "
            "WHERE inventario_origen_id = ? OR inventario_reconteo_id = ?",
            (inventario_id, inventario_id),
        )
