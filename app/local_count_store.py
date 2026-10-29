"""Persistencia MySQL del detalle de conteo móvil.

El inventario y sus totales siguen en la base principal. Solamente las cajas,
la base sobre la que se acumulan y la revision usada para evitar sobrescrituras
se guardan en tablas auxiliares de la base principal.
"""

from __future__ import annotations

from datetime import datetime
from app.mysql_store import conectar as _conectar


def inicializar_conteo_local() -> None:
    """El esquema se instala explícitamente con sql/migracion_v82.sql."""


def _caja_dict(fila) -> dict:
    return {
        "id": fila["id"],
        "cliente_uid": fila["cliente_uid"],
        "inventario_id": fila["inventario_id"],
        "item_id": fila["item_id"],
        "cantidad": float(fila["cantidad"]),
        "observacion": fila["observacion"],
        "dispositivo": fila["dispositivo"],
        "capturado_en": fila["capturado_en"],
        "creado_en": fila["creado_en"],
    }


def _actualizar_revision(conexion, inventario_id: int) -> str:
    revision = datetime.now().isoformat(timespec="microseconds")
    conexion.execute(
        """
        INSERT INTO conteo_revisiones (inventario_id, revision)
        VALUES (?, ?)
        ON CONFLICT(inventario_id) DO UPDATE SET revision = excluded.revision
        """,
        (inventario_id, revision),
    )
    return revision


def obtener_revision(inventario_id: int) -> str | None:
    with _conectar() as conexion:
        fila = conexion.execute(
            "SELECT revision FROM conteo_revisiones WHERE inventario_id = ?",
            (inventario_id,),
        ).fetchone()
    return fila["revision"] if fila else None


def listar_cajas(inventario_id: int) -> list[dict]:
    with _conectar() as conexion:
        filas = conexion.execute(
            """
            SELECT id, cliente_uid, inventario_id, item_id, cantidad,
                   observacion, dispositivo, capturado_en, creado_en
            FROM conteo_cajas
            WHERE inventario_id = ?
            ORDER BY capturado_en DESC, id DESC
            """,
            (inventario_id,),
        ).fetchall()
    return [_caja_dict(fila) for fila in filas]


def _total_objetivo(
    conexion,
    inventario_id: int,
    item_id: int,
) -> float:
    base = conexion.execute(
        """
        SELECT conteo_base FROM conteo_bases
        WHERE inventario_id = ? AND item_id = ?
        """,
        (inventario_id, item_id),
    ).fetchone()
    total = conexion.execute(
        """
        SELECT COALESCE(SUM(cantidad), 0) AS total
        FROM conteo_cajas
        WHERE inventario_id = ? AND item_id = ?
        """,
        (inventario_id, item_id),
    ).fetchone()
    return float(base["conteo_base"] if base else 0) + float(total["total"])


def registrar_caja(
    *,
    cliente_uid: str,
    inventario_id: int,
    item_id: int,
    cantidad: float,
    observacion: str,
    dispositivo: str,
    capturado_en: datetime,
    conteo_actual: float,
) -> dict:
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        existente = conexion.execute(
            "SELECT * FROM conteo_cajas WHERE cliente_uid = ?",
            (cliente_uid,),
        ).fetchone()
        if existente:
            if (
                existente["inventario_id"] != inventario_id
                or existente["item_id"] != item_id
            ):
                conexion.rollback()
                raise ValueError("El identificador de la caja ya fue utilizado")
            objetivo = _total_objetivo(conexion, inventario_id, item_id)
            conexion.commit()
            return {
                "caja": _caja_dict(existente),
                "duplicada": True,
                "conteo_fisico": objetivo,
            }

        conexion.execute(
            """
            INSERT OR IGNORE INTO conteo_bases
                (inventario_id, item_id, conteo_base)
            VALUES (?, ?, ?)
            """,
            (inventario_id, item_id, conteo_actual),
        )
        ahora = datetime.now().isoformat(timespec="seconds")
        cursor = conexion.execute(
            """
            INSERT INTO conteo_cajas (
                cliente_uid, inventario_id, item_id, cantidad, observacion,
                dispositivo, capturado_en, creado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cliente_uid,
                inventario_id,
                item_id,
                cantidad,
                observacion,
                dispositivo,
                capturado_en.isoformat(timespec="seconds"),
                ahora,
            ),
        )
        fila = conexion.execute(
            "SELECT * FROM conteo_cajas WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        objetivo = _total_objetivo(conexion, inventario_id, item_id)
        _actualizar_revision(conexion, inventario_id)
        conexion.commit()
        return {
            "caja": _caja_dict(fila),
            "duplicada": False,
            "conteo_fisico": objetivo,
        }


def eliminar_caja(inventario_id: int, caja_id: int) -> dict | None:
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        fila = conexion.execute(
            """
            SELECT * FROM conteo_cajas
            WHERE id = ? AND inventario_id = ?
            """,
            (caja_id, inventario_id),
        ).fetchone()
        if fila is None:
            conexion.commit()
            return None
        item_id = int(fila["item_id"])
        conexion.execute("DELETE FROM conteo_cajas WHERE id = ?", (caja_id,))
        objetivo = _total_objetivo(conexion, inventario_id, item_id)
        _actualizar_revision(conexion, inventario_id)
        conexion.commit()
        return {
            "caja": _caja_dict(fila),
            "conteo_fisico": objetivo,
        }


def eliminar_cajas(inventario_id: int, caja_ids: set[int]) -> dict:
    if not caja_ids:
        return {"cajas": [], "conteos": {}}
    marcas = ",".join("?" for _ in caja_ids)
    parametros = (inventario_id, *sorted(caja_ids))
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        filas = conexion.execute(
            f"""
            SELECT * FROM conteo_cajas
            WHERE inventario_id = ? AND id IN ({marcas})
            """,
            parametros,
        ).fetchall()
        if not filas:
            conexion.commit()
            return {"cajas": [], "conteos": {}}
        item_ids = {int(fila["item_id"]) for fila in filas}
        conexion.execute(
            f"DELETE FROM conteo_cajas WHERE inventario_id = ? AND id IN ({marcas})",
            parametros,
        )
        conteos = {
            item_id: _total_objetivo(conexion, inventario_id, item_id)
            for item_id in item_ids
        }
        _actualizar_revision(conexion, inventario_id)
        conexion.commit()
    return {
        "cajas": [_caja_dict(fila) for fila in filas],
        "conteos": conteos,
    }


def sincronizar_bases(inventario_id: int, conteos: dict[int, float | None]) -> None:
    """Ajusta la base si el total se edita desde la pantalla de escritorio."""
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        for item_id, conteo in conteos.items():
            existe = conexion.execute(
                """
                SELECT 1 FROM conteo_bases
                WHERE inventario_id = ? AND item_id = ?
                """,
                (inventario_id, item_id),
            ).fetchone()
            if not existe:
                continue
            total_cajas = conexion.execute(
                """
                SELECT COALESCE(SUM(cantidad), 0) AS total
                FROM conteo_cajas
                WHERE inventario_id = ? AND item_id = ?
                """,
                (inventario_id, item_id),
            ).fetchone()["total"]
            base = float(conteo or 0) - float(total_cajas)
            conexion.execute(
                """
                UPDATE conteo_bases SET conteo_base = ?
                WHERE inventario_id = ? AND item_id = ?
                """,
                (base, inventario_id, item_id),
            )
        conexion.commit()


def eliminar_items(inventario_id: int, item_ids: set[int]) -> None:
    if not item_ids:
        return
    marcas = ",".join("?" for _ in item_ids)
    parametros = (inventario_id, *sorted(item_ids))
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        conexion.execute(
            f"DELETE FROM conteo_cajas WHERE inventario_id = ? AND item_id IN ({marcas})",
            parametros,
        )
        conexion.execute(
            f"DELETE FROM conteo_bases WHERE inventario_id = ? AND item_id IN ({marcas})",
            parametros,
        )
        _actualizar_revision(conexion, inventario_id)
        conexion.commit()


def eliminar_inventario(inventario_id: int) -> None:
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        conexion.execute(
            "DELETE FROM conteo_cajas WHERE inventario_id = ?",
            (inventario_id,),
        )
        conexion.execute(
            "DELETE FROM conteo_bases WHERE inventario_id = ?",
            (inventario_id,),
        )
        conexion.execute(
            "DELETE FROM conteo_revisiones WHERE inventario_id = ?",
            (inventario_id,),
        )
        conexion.commit()
