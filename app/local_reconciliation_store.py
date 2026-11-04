"""Datos de auditoría MySQL para las conciliaciones.

Las conciliaciones y sus totales editables permanecen en DATABASE_URL. Esta
Estas tablas guardan la foto de remitos, controles/correcciones y scrap.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from uuid import uuid4
from app.mysql_store import conectar as _conectar


def inicializar_conciliaciones_local() -> None:
    """El esquema se instala explícitamente con sql/migracion_v82.sql."""
    return


def listar_codigos_excluidos(conciliacion_id: int) -> set[str]:
    with _conectar() as conexion:
        return {
            str(fila["codigo"]).strip().upper()
            for fila in conexion.execute(
                "SELECT codigo FROM conciliacion_items_excluidos WHERE conciliacion_id = ?",
                (conciliacion_id,),
            ).fetchall()
        }


def excluir_item(conciliacion_id: int, item_id: int, codigo: str) -> None:
    codigo_normalizado = codigo.strip().upper()
    with _conectar() as conexion:
        conexion.execute(
            "INSERT OR IGNORE INTO conciliacion_items_excluidos "
            "(conciliacion_id, codigo, excluido_en) VALUES (?, ?, ?)",
            (conciliacion_id, codigo_normalizado, datetime.now().isoformat(timespec="seconds")),
        )
        conexion.execute(
            "DELETE FROM conciliacion_remito_items WHERE conciliacion_id = ? AND item_id = ?",
            (conciliacion_id, item_id),
        )
        conexion.execute(
            "DELETE FROM conciliacion_ingresos_control WHERE conciliacion_id = ? AND item_id = ?",
            (conciliacion_id, item_id),
        )
        egresos = conexion.execute(
            "SELECT movimiento_clave, componentes_json FROM conciliacion_egresos_control "
            "WHERE conciliacion_id = ?",
            (conciliacion_id,),
        ).fetchall()
        for egreso in egresos:
            componentes = [
                componente for componente in _leer_json(egreso["componentes_json"])
                if int(componente.get("item_id", -1)) != item_id
                and str(componente.get("codigo", "")).strip().upper() != codigo_normalizado
            ]
            if componentes:
                conexion.execute(
                    "UPDATE conciliacion_egresos_control SET componentes_json = ? "
                    "WHERE conciliacion_id = ? AND movimiento_clave = ?",
                    (json.dumps(componentes, ensure_ascii=False), conciliacion_id, egreso["movimiento_clave"]),
                )
            else:
                conexion.execute(
                    "DELETE FROM conciliacion_egresos_control WHERE conciliacion_id = ? AND movimiento_clave = ?",
                    (conciliacion_id, egreso["movimiento_clave"]),
                )
        _reconstruir_ingresos(conexion, conciliacion_id)
        _reconstruir_egresos(conexion, conciliacion_id)


def _leer_json(valor: str) -> list:
    try:
        return json.loads(valor or "[]")
    except (TypeError, ValueError):
        return []


def _fila_control_dict(fila) -> dict:
    original = float(fila["cantidad_original"])
    editada = fila["cantidad_editada"]
    cantidad = original if editada is None else float(editada)
    return {
        "movimiento_clave": fila["movimiento_clave"],
        "item_id": int(fila["item_id"]),
        "codigo": fila["codigo"],
        "codigo_material": fila["codigo_material"],
        "remito": fila["remito"],
        "fecha": fila["fecha"],
        "cantidad": cantidad,
        "cantidad_original": original,
        "cantidad_modificada": editada is not None,
        "verificado": bool(fila["verificado"]),
        "observacion": fila["observacion"],
        "manual": bool(fila["manual"]),
    }


def _reconstruir_ingresos(conexion, conciliacion_id: int) -> None:
    filas = conexion.execute(
        """
        SELECT * FROM conciliacion_ingresos_control
        WHERE conciliacion_id = ?
        ORDER BY manual, fecha, remito, codigo_material, movimiento_clave
        """,
        (conciliacion_id,),
    ).fetchall()
    detalles = [_fila_control_dict(fila) for fila in filas]
    por_item: dict[int, list[dict]] = {}
    for detalle in detalles:
        por_item.setdefault(detalle["item_id"], []).append(detalle)
    for item_id, lineas in por_item.items():
        conexion.execute(
            """
            UPDATE conciliacion_remito_items
            SET ingresos_calculados = ?, detalle_ingresos_json = ?
            WHERE conciliacion_id = ? AND item_id = ?
            """,
            (
                sum(linea["cantidad"] for linea in lineas),
                json.dumps(lineas, ensure_ascii=False),
                conciliacion_id,
                item_id,
            ),
        )
    ids_con_detalle = set(por_item)
    for fila in conexion.execute(
        "SELECT item_id FROM conciliacion_remito_items WHERE conciliacion_id = ?",
        (conciliacion_id,),
    ).fetchall():
        if int(fila["item_id"]) not in ids_con_detalle:
            conexion.execute(
                """
                UPDATE conciliacion_remito_items
                SET ingresos_calculados = 0, detalle_ingresos_json = '[]'
                WHERE conciliacion_id = ? AND item_id = ?
                """,
                (conciliacion_id, int(fila["item_id"])),
            )
    conexion.execute(
        "UPDATE conciliacion_remitos SET remitos_ingreso_json = ? WHERE conciliacion_id = ?",
        (json.dumps(detalles, ensure_ascii=False), conciliacion_id),
    )


def _fila_egreso_dict(fila) -> dict:
    original = float(fila["cantidad_original"])
    editada = fila["cantidad_editada"]
    cantidad = original if editada is None else float(editada)
    componentes = _leer_json(fila["componentes_json"])
    for componente in componentes:
        componente["cantidad_equivalente"] = (
            cantidad * float(componente.get("uso", 0))
        )
    return {
        "movimiento_clave": fila["movimiento_clave"],
        "remito": fila["remito"],
        "remito_numero": int(fila["remito_numero"]),
        "fecha": fila["fecha"],
        "codigo_pieza": fila["codigo_pieza"],
        "cantidad": cantidad,
        "cantidad_original": original,
        "cantidad_modificada": editada is not None,
        "verificado": bool(fila["verificado"]),
        "observacion": fila["observacion"],
        "manual": bool(fila["manual"]),
        "componentes": componentes,
    }


def _reconstruir_egresos(conexion, conciliacion_id: int) -> None:
    filas = conexion.execute(
        """
        SELECT * FROM conciliacion_egresos_control
        WHERE conciliacion_id = ?
        ORDER BY manual, fecha, remito_numero, remito, codigo_pieza, movimiento_clave
        """,
        (conciliacion_id,),
    ).fetchall()
    detalles = [_fila_egreso_dict(fila) for fila in filas]
    por_item: dict[int, list[dict]] = {}
    for movimiento in detalles:
        for componente in movimiento["componentes"]:
            item_id = int(componente["item_id"])
            por_item.setdefault(item_id, []).append({
                "remito": movimiento["remito"],
                "remito_numero": movimiento["remito_numero"],
                "fecha": movimiento["fecha"],
                "pieza_origen": movimiento["codigo_pieza"],
                "cantidad_pieza": movimiento["cantidad"],
                "uso": float(componente.get("uso", 0)),
                "cantidad_equivalente": float(
                    componente.get("cantidad_equivalente", 0)
                ),
                "despacho_directo": bool(
                    componente.get("despacho_directo", False)
                ),
                "manual": movimiento["manual"],
            })
    for fila in conexion.execute(
        "SELECT item_id FROM conciliacion_remito_items WHERE conciliacion_id = ?",
        (conciliacion_id,),
    ).fetchall():
        item_id = int(fila["item_id"])
        lineas = por_item.get(item_id, [])
        conexion.execute(
            """
            UPDATE conciliacion_remito_items
            SET egresos_calculados = ?, detalle_egresos_json = ?
            WHERE conciliacion_id = ? AND item_id = ?
            """,
            (
                sum(linea["cantidad_equivalente"] for linea in lineas),
                json.dumps(lineas, ensure_ascii=False),
                conciliacion_id,
                item_id,
            ),
        )
    conexion.execute(
        "UPDATE conciliacion_remitos SET remitos_egreso_json = ? WHERE conciliacion_id = ?",
        (json.dumps(detalles, ensure_ascii=False), conciliacion_id),
    )


def guardar_auditoria(conciliacion_id: int, movimientos: dict, items: list) -> None:
    calculados_en = datetime.now().isoformat(timespec="seconds")
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        conexion.execute(
            """
            INSERT INTO conciliacion_remitos (
                conciliacion_id, remitos_ingreso_json, remitos_egreso_json,
                advertencias_json, criterio_ingreso, criterio_egreso, calculados_en
            ) VALUES (?, '[]', '[]', ?, ?, ?, ?)
            ON CONFLICT(conciliacion_id) DO UPDATE SET
                advertencias_json = excluded.advertencias_json,
                criterio_ingreso = excluded.criterio_ingreso,
                criterio_egreso = excluded.criterio_egreso,
                calculados_en = excluded.calculados_en
            """,
            (
                conciliacion_id,
                json.dumps(movimientos.get("advertencias", []), ensure_ascii=False),
                movimientos.get("criterio_ingreso", "REMITOS"),
                movimientos.get("criterio_egreso", "REMITOS"),
                calculados_en,
            ),
        )

        items_por_codigo = {item.codigo: item for item in items}
        for item in items:
            conexion.execute(
                """
                INSERT INTO conciliacion_remito_items (
                    conciliacion_id, item_id, codigo, ingresos_calculados,
                    egresos_calculados, detalle_ingresos_json, detalle_egresos_json
                ) VALUES (?, ?, ?, 0, ?, '[]', ?)
                ON CONFLICT(conciliacion_id, item_id) DO UPDATE SET
                    codigo = excluded.codigo,
                    egresos_calculados = excluded.egresos_calculados,
                    detalle_egresos_json = excluded.detalle_egresos_json
                """,
                (
                    conciliacion_id,
                    item.id,
                    item.codigo,
                    0,
                    "[]",
                ),
            )

        claves_automaticas = set()
        for posicion, detalle in enumerate(movimientos.get("ingresos", [])):
            item = items_por_codigo.get(detalle.get("codigo"))
            if item is None:
                continue
            clave = detalle.get("movimiento_clave") or (
                f"AUTO|{detalle.get('remito', '')}|{detalle.get('fecha', '')}|"
                f"{detalle.get('codigo_material', '')}|{detalle.get('codigo', '')}|{posicion}"
            )
            claves_automaticas.add(clave)
            conexion.execute(
                """
                INSERT INTO conciliacion_ingresos_control (
                    conciliacion_id, movimiento_clave, item_id, codigo,
                    codigo_material, remito, fecha, cantidad_original, manual
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(conciliacion_id, movimiento_clave) DO UPDATE SET
                    item_id = excluded.item_id,
                    codigo = excluded.codigo,
                    codigo_material = excluded.codigo_material,
                    remito = excluded.remito,
                    fecha = excluded.fecha,
                    cantidad_original = excluded.cantidad_original
                """,
                (
                    conciliacion_id, clave, item.id, item.codigo,
                    detalle.get("codigo_material", ""), detalle.get("remito", ""),
                    detalle.get("fecha", ""), float(detalle.get("cantidad", 0)),
                ),
            )

        automaticas_actuales = conexion.execute(
            """
            SELECT movimiento_clave FROM conciliacion_ingresos_control
            WHERE conciliacion_id = ? AND manual = 0
            """,
            (conciliacion_id,),
        ).fetchall()
        for fila in automaticas_actuales:
            if fila["movimiento_clave"] not in claves_automaticas:
                conexion.execute(
                    """
                    DELETE FROM conciliacion_ingresos_control
                    WHERE conciliacion_id = ? AND movimiento_clave = ? AND manual = 0
                    """,
                    (conciliacion_id, fila["movimiento_clave"]),
                )

        claves_egreso_automaticas = set()
        for posicion, detalle in enumerate(movimientos.get("egresos", [])):
            clave = detalle.get("movimiento_clave") or (
                f"AUTO|{detalle.get('remito', '')}|{detalle.get('fecha', '')}|"
                f"{detalle.get('codigo_pieza', '')}|{posicion}"
            )
            componentes = []
            for componente in detalle.get("componentes", []):
                item = items_por_codigo.get(componente.get("codigo"))
                if item is None:
                    continue
                componentes.append({
                    "item_id": int(item.id),
                    "codigo": item.codigo,
                    "uso": float(componente.get("uso", 0)),
                    "despacho_directo": bool(
                        componente.get("despacho_directo", False)
                    ),
                })
            if not componentes:
                continue
            claves_egreso_automaticas.add(clave)
            conexion.execute(
                """
                INSERT INTO conciliacion_egresos_control (
                    conciliacion_id, movimiento_clave, remito, remito_numero,
                    fecha, codigo_pieza, cantidad_original, manual,
                    componentes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                ON CONFLICT(conciliacion_id, movimiento_clave) DO UPDATE SET
                    remito = excluded.remito,
                    remito_numero = excluded.remito_numero,
                    fecha = excluded.fecha,
                    codigo_pieza = excluded.codigo_pieza,
                    cantidad_original = excluded.cantidad_original,
                    componentes_json = excluded.componentes_json
                """,
                (
                    conciliacion_id, clave, detalle.get("remito", ""),
                    int(detalle.get("remito_numero", 0)),
                    detalle.get("fecha", ""), detalle.get("codigo_pieza", ""),
                    float(detalle.get("cantidad", 0)),
                    json.dumps(componentes, ensure_ascii=False),
                ),
            )
        for fila in conexion.execute(
            """
            SELECT movimiento_clave FROM conciliacion_egresos_control
            WHERE conciliacion_id = ? AND manual = 0
            """,
            (conciliacion_id,),
        ).fetchall():
            if fila["movimiento_clave"] not in claves_egreso_automaticas:
                conexion.execute(
                    """
                    DELETE FROM conciliacion_egresos_control
                    WHERE conciliacion_id = ? AND movimiento_clave = ? AND manual = 0
                    """,
                    (conciliacion_id, fila["movimiento_clave"]),
                )

        ids_validos = {int(item.id) for item in items}
        for fila in conexion.execute(
            "SELECT movimiento_clave, item_id FROM conciliacion_ingresos_control WHERE conciliacion_id = ?",
            (conciliacion_id,),
        ).fetchall():
            if int(fila["item_id"]) not in ids_validos:
                conexion.execute(
                    "DELETE FROM conciliacion_ingresos_control WHERE conciliacion_id = ? AND movimiento_clave = ?",
                    (conciliacion_id, fila["movimiento_clave"]),
                )
        for fila in conexion.execute(
            "SELECT item_id FROM conciliacion_remito_items WHERE conciliacion_id = ?",
            (conciliacion_id,),
        ).fetchall():
            if int(fila["item_id"]) not in ids_validos:
                conexion.execute(
                    "DELETE FROM conciliacion_remito_items WHERE conciliacion_id = ? AND item_id = ?",
                    (conciliacion_id, int(fila["item_id"])),
                )
        for fila in conexion.execute(
            "SELECT movimiento_clave, componentes_json FROM conciliacion_egresos_control WHERE conciliacion_id = ?",
            (conciliacion_id,),
        ).fetchall():
            componentes = [
                componente for componente in _leer_json(fila["componentes_json"])
                if int(componente.get("item_id", -1)) in ids_validos
            ]
            if componentes:
                conexion.execute(
                    """
                    UPDATE conciliacion_egresos_control SET componentes_json = ?
                    WHERE conciliacion_id = ? AND movimiento_clave = ?
                    """,
                    (
                        json.dumps(componentes, ensure_ascii=False),
                        conciliacion_id,
                        fila["movimiento_clave"],
                    ),
                )
            else:
                conexion.execute(
                    """
                    DELETE FROM conciliacion_egresos_control
                    WHERE conciliacion_id = ? AND movimiento_clave = ?
                    """,
                    (conciliacion_id, fila["movimiento_clave"]),
                )
        _reconstruir_ingresos(conexion, conciliacion_id)
        _reconstruir_egresos(conexion, conciliacion_id)
        conexion.commit()


def actualizar_controles_ingreso(conciliacion_id: int, controles: list[dict]) -> None:
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        for control in controles:
            cantidad = float(control["cantidad"])
            cursor = conexion.execute(
                """
                UPDATE conciliacion_ingresos_control
                SET cantidad_editada = CASE
                        WHEN manual = 0 AND ABS(cantidad_original - ?) < 0.000000001
                            THEN NULL
                        ELSE ?
                    END,
                    verificado = ?, observacion = ?
                WHERE conciliacion_id = ? AND movimiento_clave = ?
                """,
                (
                    cantidad, cantidad, int(bool(control["verificado"])),
                    str(control.get("observacion", "")).strip(),
                    conciliacion_id, control["movimiento_clave"],
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("Uno de los ingresos ya no pertenece a esta conciliación")
        _reconstruir_ingresos(conexion, conciliacion_id)
        conexion.commit()


def agregar_ingreso_manual(
    conciliacion_id: int,
    item_id: int,
    codigo: str,
    codigo_material: str,
    remito: str,
    fecha: date,
    cantidad: float,
    observacion: str,
) -> None:
    clave = f"MANUAL|{uuid4().hex}"
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        conexion.execute(
            """
            INSERT INTO conciliacion_ingresos_control (
                conciliacion_id, movimiento_clave, item_id, codigo,
                codigo_material, remito, fecha, cantidad_original,
                cantidad_editada, verificado, observacion, manual
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 1)
            """,
            (
                conciliacion_id, clave, item_id, codigo, codigo_material.strip(),
                remito.strip(), fecha.isoformat(), float(cantidad), float(cantidad),
                observacion.strip(),
            ),
        )
        _reconstruir_ingresos(conexion, conciliacion_id)
        conexion.commit()


def eliminar_ingreso_manual(conciliacion_id: int, movimiento_clave: str) -> None:
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        cursor = conexion.execute(
            """
            DELETE FROM conciliacion_ingresos_control
            WHERE conciliacion_id = ? AND movimiento_clave = ? AND manual = 1
            """,
            (conciliacion_id, movimiento_clave),
        )
        if cursor.rowcount != 1:
            raise ValueError("El ingreso manual no existe o ya fue eliminado")
        _reconstruir_ingresos(conexion, conciliacion_id)
        conexion.commit()


def actualizar_controles_egreso(conciliacion_id: int, controles: list[dict]) -> None:
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        for control in controles:
            cantidad = float(control["cantidad"])
            cursor = conexion.execute(
                """
                UPDATE conciliacion_egresos_control
                SET cantidad_editada = CASE
                        WHEN manual = 0 AND ABS(cantidad_original - ?) < 0.000000001
                            THEN NULL
                        ELSE ?
                    END,
                    verificado = ?, observacion = ?
                WHERE conciliacion_id = ? AND movimiento_clave = ?
                """,
                (
                    cantidad, cantidad, int(bool(control["verificado"])),
                    str(control.get("observacion", "")).strip(),
                    conciliacion_id, control["movimiento_clave"],
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("Uno de los egresos ya no pertenece a esta conciliación")
        _reconstruir_egresos(conexion, conciliacion_id)
        conexion.commit()


def agregar_egreso_manual(
    conciliacion_id: int,
    item_id: int,
    codigo: str,
    remito: str,
    fecha: date,
    cantidad: float,
    observacion: str,
) -> None:
    clave = f"MANUAL|{uuid4().hex}"
    componentes = [{
        "item_id": int(item_id),
        "codigo": codigo,
        "uso": 1.0,
        "despacho_directo": True,
    }]
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        conexion.execute(
            """
            INSERT INTO conciliacion_egresos_control (
                conciliacion_id, movimiento_clave, remito, remito_numero,
                fecha, codigo_pieza, cantidad_original, cantidad_editada,
                verificado, observacion, manual, componentes_json
            ) VALUES (?, ?, ?, 0, ?, ?, ?, ?, 1, ?, 1, ?)
            """,
            (
                conciliacion_id, clave, remito.strip(), fecha.isoformat(), codigo,
                float(cantidad), float(cantidad), observacion.strip(),
                json.dumps(componentes, ensure_ascii=False),
            ),
        )
        _reconstruir_egresos(conexion, conciliacion_id)
        conexion.commit()


def eliminar_egreso_manual(conciliacion_id: int, movimiento_clave: str) -> None:
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        cursor = conexion.execute(
            """
            DELETE FROM conciliacion_egresos_control
            WHERE conciliacion_id = ? AND movimiento_clave = ? AND manual = 1
            """,
            (conciliacion_id, movimiento_clave),
        )
        if cursor.rowcount != 1:
            raise ValueError("El egreso manual no existe o ya fue eliminado")
        _reconstruir_egresos(conexion, conciliacion_id)
        conexion.commit()


def guardar_scrap(conciliacion_id: int, valores: dict[int, float]) -> None:
    with _conectar() as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        for item_id, scrap in valores.items():
            conexion.execute(
                """
                UPDATE conciliacion_remito_items SET scrap = ?
                WHERE conciliacion_id = ? AND item_id = ?
                """,
                (float(scrap), conciliacion_id, int(item_id)),
            )
        conexion.commit()


def obtener_auditoria(conciliacion_id: int) -> dict:
    predeterminado = {
        "remitos_ingreso": [], "remitos_egreso": [],
        "advertencias_movimientos": [], "criterio_ingreso": None,
        "criterio_egreso": None, "movimientos_calculados_en": None, "items": {},
    }
    with _conectar() as conexion:
        cabecera = conexion.execute(
            "SELECT * FROM conciliacion_remitos WHERE conciliacion_id = ?",
            (conciliacion_id,),
        ).fetchone()
        if cabecera is None:
            return predeterminado
        filas = conexion.execute(
            "SELECT * FROM conciliacion_remito_items WHERE conciliacion_id = ?",
            (conciliacion_id,),
        ).fetchall()
    return {
        "remitos_ingreso": _leer_json(cabecera["remitos_ingreso_json"]),
        "remitos_egreso": _leer_json(cabecera["remitos_egreso_json"]),
        "advertencias_movimientos": _leer_json(cabecera["advertencias_json"]),
        "criterio_ingreso": cabecera["criterio_ingreso"],
        "criterio_egreso": cabecera["criterio_egreso"],
        "movimientos_calculados_en": cabecera["calculados_en"],
        "items": {
            int(fila["item_id"]): {
                "ingresos_calculados": float(fila["ingresos_calculados"]),
                "egresos_calculados": float(fila["egresos_calculados"]),
                "scrap": float(fila["scrap"]),
                "detalle_ingresos": _leer_json(fila["detalle_ingresos_json"]),
                "detalle_egresos": _leer_json(fila["detalle_egresos_json"]),
            }
            for fila in filas
        },
    }


def eliminar_auditoria(conciliacion_id: int) -> None:
    with _conectar() as conexion:
        conexion.execute(
            "DELETE FROM conciliacion_remitos WHERE conciliacion_id = ?",
            (conciliacion_id,),
        )
        conexion.execute(
            "DELETE FROM conciliacion_items_excluidos WHERE conciliacion_id = ?",
            (conciliacion_id,),
        )
