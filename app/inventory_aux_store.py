"""Metadatos auxiliares del inventario guardados únicamente en SQLite.

No duplica el núcleo MySQL: conserva tipos de artículos mixtos en plantillas,
la procedencia de inventarios fusionados y atributos de registros de conteo.
"""

from __future__ import annotations

import sqlite3

from app.config import BASE_DIR


DATABASE_PATH = BASE_DIR / "data" / "inventarios_auxiliares.db"


def conectar() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(DATABASE_PATH, timeout=20)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA journal_mode = WAL")
    conexion.execute("PRAGMA busy_timeout = 20000")
    return conexion


def inicializar_inventarios_auxiliares() -> None:
    with conectar() as conexion:
        conexion.executescript(
            """
            CREATE TABLE IF NOT EXISTS plantilla_item_tipos (
                plantilla_id INTEGER NOT NULL,
                codigo TEXT NOT NULL,
                tipo_articulo TEXT NOT NULL CHECK (
                    tipo_articulo IN ('PIEZA', 'MATERIA_PRIMA')
                ),
                PRIMARY KEY (plantilla_id, codigo)
            );

            CREATE TABLE IF NOT EXISTS inventario_plantillas (
                inventario_id INTEGER NOT NULL,
                plantilla_id INTEGER NOT NULL,
                nombre TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (inventario_id, plantilla_id)
            );

            CREATE TABLE IF NOT EXISTS conteo_registro_meta (
                cliente_uid TEXT NOT NULL PRIMARY KEY,
                tipo_registro TEXT NOT NULL DEFAULT 'CONTEO' CHECK (
                    tipo_registro IN (
                        'CONTEO', 'CONFIRMACION_CERO', 'AJUSTE_HISTORICO'
                    )
                ),
                estado_stock TEXT NOT NULL DEFAULT 'SIN_CLASIFICAR' CHECK (
                    estado_stock IN (
                        'DISPONIBLE', 'LINEA', 'RETENIDO', 'SCRAP',
                        'SIN_CLASIFICAR'
                    )
                )
            );

            CREATE INDEX IF NOT EXISTS ix_inventario_plantillas_inventario
                ON inventario_plantillas(inventario_id);
            """
        )


def tipos_items_plantilla(plantilla_id: int) -> dict[str, str]:
    with conectar() as conexion:
        filas = conexion.execute(
            """SELECT codigo, tipo_articulo FROM plantilla_item_tipos
               WHERE plantilla_id = ?""",
            (plantilla_id,),
        ).fetchall()
    return {str(fila["codigo"]).upper(): fila["tipo_articulo"] for fila in filas}


def guardar_tipos_items_plantilla(
    plantilla_id: int,
    tipos: dict[str, str],
) -> None:
    with conectar() as conexion:
        conexion.execute(
            "DELETE FROM plantilla_item_tipos WHERE plantilla_id = ?",
            (plantilla_id,),
        )
        conexion.executemany(
            """INSERT INTO plantilla_item_tipos (
                   plantilla_id, codigo, tipo_articulo
               ) VALUES (?, ?, ?)""",
            [
                (plantilla_id, codigo.strip().upper(), tipo)
                for codigo, tipo in tipos.items()
            ],
        )


def eliminar_metadatos_plantilla(plantilla_id: int) -> None:
    with conectar() as conexion:
        conexion.execute(
            "DELETE FROM plantilla_item_tipos WHERE plantilla_id = ?",
            (plantilla_id,),
        )


def guardar_plantillas_inventario(
    inventario_id: int,
    plantillas: list[tuple[int, str]],
) -> None:
    with conectar() as conexion:
        conexion.execute(
            "DELETE FROM inventario_plantillas WHERE inventario_id = ?",
            (inventario_id,),
        )
        conexion.executemany(
            """INSERT INTO inventario_plantillas (
                   inventario_id, plantilla_id, nombre
               ) VALUES (?, ?, ?)""",
            [(inventario_id, plantilla_id, nombre) for plantilla_id, nombre in plantillas],
        )


def plantillas_inventario(inventario_id: int) -> list[dict]:
    with conectar() as conexion:
        filas = conexion.execute(
            """SELECT plantilla_id, nombre FROM inventario_plantillas
               WHERE inventario_id = ? ORDER BY nombre, plantilla_id""",
            (inventario_id,),
        ).fetchall()
    return [dict(fila) for fila in filas]


def guardar_meta_registro(
    cliente_uid: str,
    tipo_registro: str,
    estado_stock: str,
) -> None:
    with conectar() as conexion:
        conexion.execute(
            """INSERT INTO conteo_registro_meta (
                   cliente_uid, tipo_registro, estado_stock
               ) VALUES (?, ?, ?)
               ON CONFLICT(cliente_uid) DO UPDATE SET
                   tipo_registro = excluded.tipo_registro,
                   estado_stock = excluded.estado_stock""",
            (cliente_uid, tipo_registro, estado_stock),
        )


def metas_registros(cliente_uids: list[str]) -> dict[str, dict]:
    if not cliente_uids:
        return {}
    marcas = ",".join("?" for _ in cliente_uids)
    with conectar() as conexion:
        filas = conexion.execute(
            f"""SELECT cliente_uid, tipo_registro, estado_stock
                FROM conteo_registro_meta
                WHERE cliente_uid IN ({marcas})""",
            cliente_uids,
        ).fetchall()
    return {fila["cliente_uid"]: dict(fila) for fila in filas}


def eliminar_meta_registros(cliente_uids: list[str]) -> None:
    if not cliente_uids:
        return
    marcas = ",".join("?" for _ in cliente_uids)
    with conectar() as conexion:
        conexion.execute(
            f"DELETE FROM conteo_registro_meta WHERE cliente_uid IN ({marcas})",
            cliente_uids,
        )


def eliminar_metadatos_inventario(inventario_id: int) -> None:
    with conectar() as conexion:
        conexion.execute(
            "DELETE FROM inventario_plantillas WHERE inventario_id = ?",
            (inventario_id,),
        )
