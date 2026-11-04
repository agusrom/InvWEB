"""Persistencia del detalle de conteo compartido por PC y móvil.

El inventario, las cajas y sus totales siguen en la base principal. Los nuevos
atributos de auditoría y estado de stock se guardan en SQLite para no alterar
el esquema MySQL existente.
"""

from __future__ import annotations

from datetime import datetime
import re

from app.inventory_aux_store import (
    eliminar_meta_registros,
    guardar_meta_registro,
    metas_registros,
)
from app.mysql_store import conectar as _conectar


ESTADOS_STOCK = {
    "DISPONIBLE", "LINEA", "RETENIDO", "SCRAP", "SIN_CLASIFICAR",
}
PREFIJO_ESTADO = re.compile(
    r"^\[(DISPONIBLE|LINEA|RETENIDO|SCRAP)\]\s*",
    flags=re.IGNORECASE,
)


def normalizar_estado_stock(valor: str | None, observacion: str = "") -> str:
    estado = str(valor or "").strip().upper()
    if estado in ESTADOS_STOCK - {"SIN_CLASIFICAR"}:
        return estado
    legado = PREFIJO_ESTADO.match(str(observacion or "").strip())
    return legado.group(1).upper() if legado else "SIN_CLASIFICAR"


def inicializar_conteo_local() -> None:
    """Convierte bases PC históricas en renglones, sin agregar tablas MySQL."""
    ahora = datetime.now().isoformat(timespec="seconds")
    metadatos: list[tuple[str, str]] = []
    with _conectar() as conexion:
        filas = conexion.execute(
            """
            SELECT ii.id AS item_id, ii.inventario_id, ii.conteo_fisico,
                   COALESCE(SUM(cc.cantidad), 0) AS total_registros,
                   COUNT(cc.id) AS cantidad_registros
            FROM inventario_items ii
            INNER JOIN inventarios i ON i.id = ii.inventario_id
            LEFT JOIN conteo_cajas cc
              ON cc.inventario_id = ii.inventario_id AND cc.item_id = ii.id
            WHERE ii.conteo_fisico IS NOT NULL
              AND COALESCE(i.modalidad_conteo, 'ESTANDAR') <> 'MEDIOS'
            GROUP BY ii.id, ii.inventario_id, ii.conteo_fisico
            """
        ).fetchall()
        for fila in filas:
            fisico = float(fila["conteo_fisico"])
            total = float(fila["total_registros"])
            cantidad = int(fila["cantidad_registros"])
            diferencia = fisico - total
            uid = f"migracion-pc-{fila['inventario_id']}-{fila['item_id']}"
            if cantidad == 0 and abs(fisico) <= 0.000000001:
                conexion.execute(
                    """INSERT OR IGNORE INTO conteo_cajas (
                           cliente_uid, inventario_id, item_id, cantidad,
                           observacion, dispositivo, capturado_en, creado_en
                       ) VALUES (?, ?, ?, 0, ?, 'MIGRACION', ?, ?)""",
                    (
                        uid, fila["inventario_id"], fila["item_id"],
                        "Físico cero verificado (migrado)", ahora, ahora,
                    ),
                )
                metadatos.append((uid, "CONFIRMACION_CERO"))
            elif abs(diferencia) > 0.000000001:
                conexion.execute(
                    """INSERT OR IGNORE INTO conteo_cajas (
                           cliente_uid, inventario_id, item_id, cantidad,
                           observacion, dispositivo, capturado_en, creado_en
                       ) VALUES (?, ?, ?, ?, ?, 'MIGRACION', ?, ?)""",
                    (
                        uid, fila["inventario_id"], fila["item_id"], diferencia,
                        "Migrado desde total directo de PC", ahora, ahora,
                    ),
                )
                metadatos.append((uid, "AJUSTE_HISTORICO"))
        conexion.execute("UPDATE conteo_bases SET conteo_base = 0")
        conexion.commit()
    for uid, tipo in metadatos:
        guardar_meta_registro(uid, tipo, "SIN_CLASIFICAR")


def _caja_dict(fila, meta: dict | None = None) -> dict:
    meta = meta or {}
    return {
        "id": fila["id"],
        "cliente_uid": fila["cliente_uid"],
        "inventario_id": fila["inventario_id"],
        "item_id": fila["item_id"],
        "cantidad": float(fila["cantidad"]),
        "tipo_registro": meta.get("tipo_registro", "CONTEO"),
        "estado_stock": normalizar_estado_stock(
            meta.get("estado_stock"), fila["observacion"],
        ),
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
    metas = metas_registros([fila["cliente_uid"] for fila in filas])
    return [
        _caja_dict(fila, metas.get(fila["cliente_uid"])) for fila in filas
    ]


def _total_objetivo(
    conexion,
    inventario_id: int,
    item_id: int,
) -> float | None:
    base = conexion.execute(
        """
        SELECT conteo_base FROM conteo_bases
        WHERE inventario_id = ? AND item_id = ?
        """,
        (inventario_id, item_id),
    ).fetchone()
    total = conexion.execute(
        """
        SELECT COALESCE(SUM(cantidad), 0) AS total, COUNT(*) AS cantidad
        FROM conteo_cajas
        WHERE inventario_id = ? AND item_id = ?
        """,
        (inventario_id, item_id),
    ).fetchone()
    valor_base = float(base["conteo_base"] if base else 0)
    if int(total["cantidad"]) == 0 and abs(valor_base) <= 0.000000001:
        return None
    return valor_base + float(total["total"])


def totales_conteo_por_item(inventario_id: int) -> dict[int, float]:
    """Fuente única del físico: renglones auditables del conteo."""
    with _conectar() as conexion:
        filas = conexion.execute(
            """SELECT item_id, COALESCE(SUM(cantidad), 0) AS total
               FROM conteo_cajas WHERE inventario_id = ? GROUP BY item_id""",
            (inventario_id,),
        ).fetchall()
    return {int(fila["item_id"]): float(fila["total"]) for fila in filas}


def registrar_caja(
    *,
    cliente_uid: str,
    inventario_id: int,
    item_id: int,
    cantidad: float,
    tipo_registro: str,
    estado_stock: str,
    observacion: str,
    dispositivo: str,
    capturado_en: datetime,
    conteo_actual: float,
) -> dict:
    tipo_registro = str(tipo_registro or "CONTEO").strip().upper()
    if tipo_registro not in {"CONTEO", "CONFIRMACION_CERO"}:
        raise ValueError("Tipo de registro inválido")
    if tipo_registro == "CONTEO" and cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero")
    if tipo_registro == "CONFIRMACION_CERO" and cantidad != 0:
        raise ValueError("Una confirmación de cero debe tener cantidad cero")
    estado_stock = normalizar_estado_stock(estado_stock, observacion)
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
                "caja": _caja_dict(
                    existente,
                    metas_registros([cliente_uid]).get(cliente_uid),
                ),
                "duplicada": True,
                "conteo_fisico": objetivo,
            }

        conexion.execute(
            """
            INSERT OR IGNORE INTO conteo_bases
                (inventario_id, item_id, conteo_base)
            VALUES (?, ?, ?)
            """,
            (inventario_id, item_id, 0),
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
        guardar_meta_registro(cliente_uid, tipo_registro, estado_stock)
        return {
            "caja": _caja_dict(
                fila,
                {"tipo_registro": tipo_registro, "estado_stock": estado_stock},
            ),
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
        eliminar_meta_registros([fila["cliente_uid"]])
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
    eliminar_meta_registros([fila["cliente_uid"] for fila in filas])
    return {
        "cajas": [_caja_dict(fila) for fila in filas],
        "conteos": conteos,
    }


def eliminar_items(inventario_id: int, item_ids: set[int]) -> None:
    if not item_ids:
        return
    marcas = ",".join("?" for _ in item_ids)
    parametros = (inventario_id, *sorted(item_ids))
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        filas = conexion.execute(
            f"""SELECT cliente_uid FROM conteo_cajas
                WHERE inventario_id = ? AND item_id IN ({marcas})""",
            parametros,
        ).fetchall()
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
    eliminar_meta_registros([fila["cliente_uid"] for fila in filas])


def eliminar_inventario(inventario_id: int) -> None:
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        filas = conexion.execute(
            "SELECT cliente_uid FROM conteo_cajas WHERE inventario_id = ?",
            (inventario_id,),
        ).fetchall()
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
    eliminar_meta_registros([fila["cliente_uid"] for fila in filas])
