"""Retiro explícito y repetible de tablas de Conciliaciones de prueba.

Sin --apply solamente inspecciona e imprime SQL. Nunca usa la conexión productiva.
Los DDL de MySQL no son reversibles por ROLLBACK: requiere respaldo previo.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEGACY_TABLES = (
    "conciliacion_remito_items", "conciliacion_ingresos_control",
    "conciliacion_egresos_control", "conciliacion_items_excluidos",
    "conciliacion_remitos", "conciliacion_items", "conciliaciones",
)
PROTECTED_TABLES = (
    "inventarios", "inventario_items", "plantillas", "plantilla_items",
    "programaciones_inventario", "conteo_cajas", "conteo_bases",
    "conteo_revisiones", "inventarios_relaciones", "inventario_cierres",
    "programacion_cierres", "inventario_programaciones",
)


def quote(name):
    return "`" + name.replace("`", "``") + "`"


def build_plan(database, tables, foreign_keys, nullable_legacy_link=True):
    retired = set(LEGACY_TABLES) & set(tables)
    commands = []
    dependencies = {table: set() for table in retired}
    detach = set()
    for fk in foreign_keys:
        if fk["referenced_table"] not in retired or fk["referenced_schema"] != database:
            continue
        table = fk["table_name"]
        if fk["table_schema"] == database and table in retired:
            dependencies[fk["referenced_table"]].add(table)
        elif (fk["table_schema"] == database and table == "analisis_stock"
              and fk["column_name"] == "conciliacion_legacy_id"
              and fk["referenced_table"] == "conciliaciones" and nullable_legacy_link):
            detach.add(fk["constraint_name"])
        else:
            raise RuntimeError(f"Dependencia no prevista: {fk['table_schema']}.{table}.{fk['column_name']}. No se ejecutó el plan.")
    if detach:
        commands.append("UPDATE `analisis_stock` SET `conciliacion_legacy_id` = NULL WHERE `conciliacion_legacy_id` IS NOT NULL")
        commands.extend(f"ALTER TABLE `analisis_stock` DROP FOREIGN KEY {quote(name)}" for name in sorted(detach))
    pending = set(retired)
    while pending:
        ready = [table for table in LEGACY_TABLES if table in pending and not (dependencies[table] & pending)]
        if not ready:
            raise RuntimeError("Dependencias circulares entre tablas de prueba. No se ejecutó el plan.")
        for table in ready:
            commands.append(f"DROP TABLE {quote(table)}")
            pending.remove(table)
    return commands


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database")
    parser.add_argument("--backup-confirmed", action="store_true")
    args = parser.parse_args()
    from sqlalchemy import inspect, text
    from app.database import engine
    if engine.dialect.name != "mysql":
        parser.error("DATABASE_URL debe apuntar a la base MySQL de gestión")
    with engine.connect() as db:
        database = db.execute(text("SELECT DATABASE()")).scalar_one()
        tables = set(inspect(db).get_table_names())
        if not {"inventarios", "inventario_items"} <= tables:
            parser.error("La base seleccionada no tiene las tablas de inventarios esperadas")
        keys = db.execute(text("""SELECT TABLE_SCHEMA AS table_schema, TABLE_NAME AS table_name,
            CONSTRAINT_NAME AS constraint_name, COLUMN_NAME AS column_name,
            REFERENCED_TABLE_NAME AS referenced_table, REFERENCED_TABLE_SCHEMA AS referenced_schema
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE REFERENCED_TABLE_SCHEMA = :database"""), {"database": database}).mappings().all()
        nullable = any(col["name"] == "conciliacion_legacy_id" and col["nullable"]
                       for col in inspect(db).get_columns("analisis_stock")) if "analisis_stock" in tables else True
        commands = build_plan(database, tables, keys, nullable)
        print(f"Base de gestión: {database}")
        for table in LEGACY_TABLES:
            if table in tables:
                count = db.execute(text(f"SELECT COUNT(*) FROM {quote(table)}")).scalar_one()
                print(f"-- Retirar {table}: {count} registros de prueba")
        for command in commands:
            print(command + ";")
        if not args.apply:
            print("Solo inspección. No se modificaron datos.")
            return
        if args.confirm_database != database or not args.backup_confirmed:
            parser.error("Para aplicar: --confirm-database NOMBRE_REAL --backup-confirmed (tras comprobar el respaldo)")
        counts = {table: db.execute(text(f"SELECT COUNT(*) FROM {quote(table)}")).scalar_one()
                  for table in PROTECTED_TABLES if table in tables}
        db.commit()
        for command in commands:
            db.execute(text(command))
            db.commit()
        for table, before in counts.items():
            after = db.execute(text(f"SELECT COUNT(*) FROM {quote(table)}")).scalar_one()
            if before != after:
                raise RuntimeError(f"Cambió la cantidad de registros en {table}: {before} -> {after}. Revisar respaldo.")
        print("Retiro terminado. Cantidades de inventarios y tablas protegidas conservadas.")


if __name__ == "__main__":
    main()
