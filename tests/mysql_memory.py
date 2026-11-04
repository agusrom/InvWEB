"""Doble MySQL mínimo para probar almacenes auxiliares sin una base real."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Cursor:
    rows: list[dict]
    rowcount: int = 0

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class Connection:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        query = " ".join(sql.lower().split())
        if query.startswith("select datos_json from analisis_stock_auditoria"):
            value = self.state["audits"].get(int(params[0]))
            return Cursor([{"datos_json": value}] if value is not None else [])
        if query.startswith("insert ignore into analisis_stock_auditoria"):
            self.state["audits"].setdefault(int(params[0]), params[1])
            return Cursor([], 1)
        if query.startswith("insert into analisis_stock_auditoria"):
            self.state["audits"][int(params[0])] = params[1]
            return Cursor([], 1)
        if query.startswith("delete from analisis_stock_iniciales"):
            self.state["initials"].pop(str(params[0]), None)
            return Cursor([], 1)
        if query.startswith("insert into analisis_stock_iniciales"):
            self.state["initials"].setdefault(str(params[0]), []).append(int(params[1]))
            return Cursor([], 1)
        if query.startswith("select id, creado_en from analisis_stock"):
            final_id, signature = int(params[0]), params[1]
            rows = [
                {"id": row["id"], "creado_en": row["creado_en"]}
                for row in self.state["analyses"].values()
                if row["inventario_final_id"] == final_id
                and row["firma_iniciales"] == signature
            ]
            return Cursor(rows)
        if query.startswith("select id from analisis_stock where conciliacion_legacy_id"):
            rows = [
                {"id": row["id"]}
                for row in self.state["analyses"].values()
                if row["conciliacion_legacy_id"] == params[0]
            ]
            return Cursor(rows)
        if query.startswith("select id from analisis_stock where inventario_final_id"):
            final_id, signature = int(params[0]), params[1]
            rows = [
                {"id": row["id"]}
                for row in self.state["analyses"].values()
                if row["inventario_final_id"] == final_id
                and row["firma_iniciales"] == signature
            ]
            return Cursor(rows)
        if query.startswith("insert into analisis_stock ("):
            keys = (
                "id", "inventario_final_id", "firma_iniciales", "iniciales_json",
                "nombre", "origen", "conciliacion_legacy_id", "creado_en",
                "actualizado_en", "calculo_json",
            )
            if len(params) == 8:  # save_analysis fija origen y legacy en SQL
                values = (
                    params[0], params[1], params[2], params[3], params[4],
                    "NUEVO", None, params[5], params[6], params[7],
                )
            else:
                values = params
            row = dict(zip(keys, values))
            self.state["analyses"][str(row["id"])] = row
            return Cursor([], 1)
        if query.startswith("select id, inventario_final_id") and "from analisis_stock where id" in query:
            row = self.state["analyses"].get(str(params[0]))
            return Cursor([dict(row)] if row else [])
        if query.startswith("select id, inventario_final_id") and "from analisis_stock order by" in query:
            rows = sorted(
                (dict(row) for row in self.state["analyses"].values()),
                key=lambda row: row["actualizado_en"],
                reverse=True,
            )
            return Cursor(rows)
        if query.startswith("delete from analisis_stock where id"):
            existed = self.state["analyses"].pop(str(params[0]), None) is not None
            return Cursor([], 1 if existed else 0)
        if query.startswith("select codigo, causa_codigo"):
            final_id = int(params[0])
            rows = [
                dict(row)
                for (stored_final, _code), row in self.state["notes"].items()
                if stored_final == final_id
            ]
            return Cursor(sorted(rows, key=lambda row: row["codigo"]))
        if query.startswith("insert into analisis_stock_notas"):
            row = {
                "inventario_final_id": int(params[0]),
                "codigo": params[1],
                "causa_codigo": params[2],
                "observacion": params[3],
                "estado": params[4],
                "controles_json": params[5],
            }
            self.state["notes"][(row["inventario_final_id"], row["codigo"])] = row
            return Cursor([], 1)
        raise AssertionError(f"SQL no implementado en el doble de prueba: {query}")


class MemoryMySQL:
    def __init__(self):
        self.state = {
            "audits": {}, "analyses": {}, "initials": {}, "notes": {},
        }

    def connect(self):
        return Connection(self.state)
