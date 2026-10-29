"""Auditoría compartida por inventario final, independiente de la conciliación vieja.

SQLite se usa exclusivamente para este archivo auxiliar: transacciones entre
procesos, sin cambiar DATABASE_URL ni las tablas MySQL existentes.
"""
from contextlib import contextmanager, closing
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from datetime import datetime
from uuid import uuid4

STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "preconciliacion_auditoria.sqlite3"


@contextmanager
def connection():
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(STORE_PATH, timeout=30)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS auditoria (final_id INTEGER PRIMARY KEY, datos TEXT NOT NULL)")
        db.execute("""CREATE TABLE IF NOT EXISTS analisis (
            id TEXT PRIMARY KEY, final_id INTEGER NOT NULL, iniciales TEXT NOT NULL,
            nombre TEXT NOT NULL, creado_en TEXT NOT NULL, actualizado_en TEXT NOT NULL,
            calculo TEXT NOT NULL, UNIQUE(final_id, iniciales)
        )""")
        db.execute("BEGIN IMMEDIATE")
        yield db


def read(db, final_id):
    row = db.execute("SELECT datos FROM auditoria WHERE final_id = ?", (final_id,)).fetchone()
    return json.loads(row[0]) if row else {"movimientos": {}, "scrap": {}}


def write(db, final_id, data):
    db.execute("INSERT OR REPLACE INTO auditoria VALUES (?, ?)", (final_id, json.dumps(data, ensure_ascii=False)))


def save_analysis(final_id, final_code, scenarios, calculation, name=None):
    initial_ids = sorted(int(item["inicial"]["id"]) for item in scenarios)
    initial_codes = [item["inicial"]["codigo"] for item in scenarios]
    signature = json.dumps(initial_ids, separators=(",", ":"))
    now = datetime.now().isoformat(timespec="seconds")
    with connection() as db:
        existing = db.execute(
            "SELECT id, creado_en FROM analisis WHERE final_id=? AND iniciales=?",
            (final_id, signature),
        ).fetchone()
        analysis_id = existing[0] if existing else uuid4().hex
        created = existing[1] if existing else now
        name = str(name or f"{final_code} · desde {', '.join(initial_codes)}").strip()
        db.execute(
            "INSERT OR REPLACE INTO analisis VALUES (?, ?, ?, ?, ?, ?, ?)",
            (analysis_id, final_id, signature, name, created, now,
             json.dumps(calculation, ensure_ascii=False)),
        )
    return analysis_id


def list_analyses(include_calculation=False):
    with connection() as db:
        rows = db.execute(
            "SELECT id, final_id, iniciales, nombre, creado_en, actualizado_en, calculo "
            "FROM analisis ORDER BY actualizado_en DESC"
        ).fetchall()
    result = []
    for row in rows:
        item = {"id": row[0], "final_id": row[1], "inventarios_iniciales": json.loads(row[2]),
                "nombre": row[3], "creado_en": row[4], "actualizado_en": row[5]}
        if include_calculation:
            item["calculo"] = json.loads(row[6])
        result.append(item)
    return result


def get_analysis(analysis_id):
    with connection() as db:
        row = db.execute(
            "SELECT id, final_id, iniciales, nombre, creado_en, actualizado_en, calculo "
            "FROM analisis WHERE id=?", (analysis_id,),
        ).fetchone()
    if not row:
        return None
    return {"id": row[0], "final_id": row[1], "inventarios_iniciales": json.loads(row[2]),
            "nombre": row[3], "creado_en": row[4], "actualizado_en": row[5],
            "calculo": json.loads(row[6])}


def delete_analysis(analysis_id):
    """Elimina únicamente la instantánea guardada, no la auditoría compartida."""
    with connection() as db:
        cursor = db.execute("DELETE FROM analisis WHERE id = ?", (analysis_id,))
        return cursor.rowcount > 0


def edit(final_id, key, changes=None, delete=False):
    with connection() as db:
        data = read(db, final_id)
        movement = data["movimientos"].get(key)
        if movement is None:
            raise ValueError("Movimiento inexistente; calculá los escenarios primero")
        if delete:
            if not movement.get("manual"):
                raise ValueError("Solo se pueden eliminar movimientos manuales")
            del data["movimientos"][key]
        else:
            movement.update(changes)
        write(db, final_id, data)
    return {"ok": True}


def edit_many(final_id, controls):
    """Guarda de forma atómica todos los renglones de un mismo remito.

    Devuelve si cambió un valor que participa de la conciliación. Verificación
    y observación son datos de auditoría y no justifican recalcular estructuras
    ni volver a consultar los remitos.
    """
    if not controls:
        raise ValueError("El remito no contiene movimientos para guardar")
    keys = [str(control.get("clave", "")) for control in controls]
    if len(keys) != len(set(keys)):
        raise ValueError("No repitas movimientos dentro del mismo remito")
    with connection() as db:
        data = read(db, final_id)
        movements = data["movimientos"]
        missing = [key for key in keys if key not in movements]
        if missing:
            raise ValueError("Uno de los movimientos ya no existe; recalculá el análisis")
        groups = {
            (
                str(movements[key].get("tipo", "")),
                str(movements[key].get("remito", "")).strip().upper(),
            )
            for key in keys
        }
        if len(groups) != 1:
            raise ValueError("Sólo se puede guardar un remito por operación")

        requires_recalculation = False
        saved = []
        for control in controls:
            movement = movements[control["clave"]]
            edited_quantity = control.get("cantidad_editada")
            excluded = sorted(set(int(item) for item in (control.get("excluidos") or [])))
            if movement.get("cantidad_editada") != edited_quantity:
                requires_recalculation = True
            if sorted(set(movement.get("excluidos") or [])) != excluded:
                requires_recalculation = True
            movement.update({
                "cantidad_editada": edited_quantity,
                "verificado": bool(control.get("verificado", False)),
                "observacion": str(control.get("observacion", "")),
                "excluidos": excluded,
            })
            saved.append({
                "clave": control["clave"],
                "cantidad_editada": movement["cantidad_editada"],
                "cantidad": (
                    movement["cantidad_editada"]
                    if movement["cantidad_editada"] is not None
                    else movement["cantidad_original"]
                ),
                "verificado": movement["verificado"],
                "observacion": movement["observacion"],
                "excluidos": movement["excluidos"],
            })
        write(db, final_id, data)
    return {
        "ok": True,
        "requiere_recalculo": requires_recalculation,
        "movimientos": saved,
    }


def add_manual(final_id, movement):
    key = "MANUAL-" + uuid4().hex
    with connection() as db:
        data = read(db, final_id)
        data["movimientos"][key] = dict(movement, clave=key, manual=True,
            cantidad_original=movement["cantidad"], cantidad_editada=None,
            verificado=False, excluidos=[], escenarios=[])
        write(db, final_id, data)
    return {"clave": key}


def set_scrap(final_id, initial_id, code, quantity):
    with connection() as db:
        data = read(db, final_id)
        data["scrap"].setdefault(str(initial_id), {})[code.strip().upper()] = quantity
        write(db, final_id, data)
    return {"ok": True}


def source_key(kind, row):
    # La identidad no incluye cantidad ni escenario; una corrección sobrevive
    # al recálculo. El ingreso por material se comparte entre sus destinos.
    code = row.get("codigo_material", row.get("codigo", "")) if kind == "IN" else row["pieza_origen"]
    identity = [kind, str(row.get("remito", "")), str(row.get("fecha", "")), code]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()


def reconcile(final_id, final_date, scenarios, tolerance, within, resolve_manual):
    """Registra fuentes una vez y aplica controles a todos sus escenarios."""
    with connection() as db:
        data = read(db, final_id)
        movements = data["movimientos"]
        present = {}
        for scenario in scenarios:
            sid = scenario["inicial"]["id"]
            for row in scenario["filas"]:
                for kind, field in (("IN", "detalle_ingresos"), ("OUT", "detalle_egresos")):
                    for detail in row[field]:
                        key = source_key(kind, detail)
                        original = detail["cantidad"] if kind == "IN" else detail["cantidad_pieza"]
                        old = movements.get(key, {})
                        source_changed = bool(old) and old.get("cantidad_original") != original
                        movements[key] = dict(old, clave=key, tipo=kind,
                            remito=detail.get("remito", ""), fecha=detail.get("fecha", ""),
                            codigo=detail.get("codigo_material", row["codigo"]) if kind == "IN" else detail["pieza_origen"],
                            cantidad_original=original, manual=False)
                        if source_changed:
                            movements[key]["verificado"] = False
                            warning = f"El origen cambió la cantidad de {detail.get('remito', 'sin remito')}; se anuló su verificación."
                            if warning not in scenario["advertencias"]:
                                scenario["advertencias"].append(warning)
                        detail["clave"] = key
                        present.setdefault(key, set()).add(sid)
        for movement in movements.values():
            if movement.get("manual"):
                present[movement["clave"]] = {
                    s["inicial"]["id"] for s in scenarios
                    if not s.get("error") and str(s["inicial"]["fecha"])[:10] < movement["fecha"] <= str(final_date)[:10]
                }
        for scenario in scenarios:
            sid = scenario["inicial"]["id"]
            codes = {r["codigo"] for r in scenario["filas"]}
            for movement in movements.values():
                if not movement.get("manual") or sid not in present.get(movement["clave"], set()):
                    continue
                if sid in movement.get("excluidos", []):
                    continue
                uses = resolve_manual(movement, codes)
                if not uses:
                    scenario["advertencias"].append(f"Manual {movement['remito']} ({movement['codigo']}): sin pieza comparable; no suma en este escenario.")
                for row in scenario["filas"]:
                    if row["codigo"] not in uses:
                        continue
                    detail = dict(movement, cantidad=movement["cantidad_original"],
                        cantidad_pieza=movement["cantidad_original"], pieza_origen=movement["codigo"], uso=uses[row["codigo"]])
                    row["detalle_ingresos" if movement["tipo"] == "IN" else "detalle_egresos"].append(detail)
            for row in scenario["filas"]:
                for kind, field, total in (("IN", "detalle_ingresos", "ingresos"), ("OUT", "detalle_egresos", "egresos")):
                    effective = []
                    for detail in row[field]:
                        movement = movements[detail["clave"]]
                        if sid in movement.get("excluidos", []):
                            continue
                        quantity = movement.get("cantidad_editada")
                        if quantity is None:
                            quantity = movement["cantidad_original"]
                        detail.update(verificado=movement.get("verificado", False), observacion=movement.get("observacion", ""))
                        if kind == "IN":
                            detail["cantidad"] = quantity
                        else:
                            detail["cantidad_pieza"] = quantity
                            detail["cantidad_equivalente"] = quantity * detail["uso"]
                        effective.append(detail)
                    row[field] = effective
                    row[total] = sum(d["cantidad" if kind == "IN" else "cantidad_equivalente"] for d in effective)
                row["scrap"] = data["scrap"].get(str(sid), {}).get(row["codigo"], 0)
                row["esperado"] = row["fisico_inicial"] + row["ingresos"] - row["egresos"] - row["scrap"]
                explotado_actual = row.get("conteo_explotado_actual", row["fisico_actual"])
                row["diferencia_conciliacion"] = explotado_actual - row["esperado"]
                row["porcentaje_desvio_conciliacion"] = (
                    (explotado_actual - row["esperado"]) * 100 / row["esperado"]
                    if row["esperado"] else (0.0 if explotado_actual == 0 else None)
                )
                row["conciliacion_ok"] = within(explotado_actual, row["esperado"], tolerance)
        # Conserva auditorías de escenarios no seleccionados, sin mostrarlas
        # como participantes en el cálculo actual.
        result = []
        for key, movement in movements.items():
            if key not in present and not movement.get("manual"):
                continue
            item = deepcopy(movement)
            item["escenarios"] = sorted(present.get(key, set()))
            item["cantidad"] = item.get("cantidad_editada") if item.get("cantidad_editada") is not None else item["cantidad_original"]
            result.append(item)
        write(db, final_id, data)
    return {"escenarios": scenarios, "tolerancia": tolerance, "movimientos": result}
