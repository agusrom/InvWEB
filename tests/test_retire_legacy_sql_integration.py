"""Ejecuta el .sql real en una base efímera MySQL/MariaDB.

Opt-in: INVWEB_SQL_TEST_PORT y opcionalmente HOST, USER, PASSWORD con el mismo
prefijo. Usar una instancia de pruebas: requiere CREATE/DROP DATABASE y rutinas.
No reutiliza DATABASE_URL ni selecciona una base existente de la aplicación.
"""
import os
from pathlib import Path
from uuid import uuid4
import unittest
import pymysql
from scripts.retirar_modulos_prueba import LEGACY_TABLES, PROTECTED_TABLES

SQL = (Path(__file__).resolve().parents[1] / "sql/etapa1_retirar_modulos_prueba.sql").read_text()


def statements(script):
    delimiter = ";"
    buffer = []
    for line in script.splitlines():
        if line.strip().upper().startswith("DELIMITER "):
            delimiter = line.strip().split()[1]
            continue
        buffer.append(line)
        if line.rstrip().endswith(delimiter):
            yield "\n".join(buffer).rstrip()[:-len(delimiter)]
            buffer = []
    if "\n".join(buffer).strip():
        raise AssertionError("SQL incompleto")


@unittest.skipUnless(os.getenv("INVWEB_SQL_TEST_PORT"), "Requiere instancia MySQL/MariaDB de pruebas explícita")
class RetireLegacySqlIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.db = pymysql.connect(host=os.getenv("INVWEB_SQL_TEST_HOST", "127.0.0.1"),
                                 port=int(os.environ["INVWEB_SQL_TEST_PORT"]),
                                 user=os.getenv("INVWEB_SQL_TEST_USER", "root"),
                                 password=os.getenv("INVWEB_SQL_TEST_PASSWORD", ""),
                                 charset="utf8mb4", autocommit=True)
        self.schema = "invweb_sql_test_" + uuid4().hex
        with self.db.cursor() as cur:
            cur.execute(f"CREATE DATABASE `{self.schema}` CHARACTER SET utf8mb4")
        self.db.select_db(self.schema)
        with self.db.cursor() as cur:
            cur.execute("CREATE TABLE inventarios (id BIGINT PRIMARY KEY, dato VARCHAR(30)) ENGINE=InnoDB")
            cur.execute("CREATE TABLE inventario_items (id BIGINT PRIMARY KEY, inventario_id BIGINT, cantidad DECIMAL(18,4), FOREIGN KEY (inventario_id) REFERENCES inventarios(id)) ENGINE=InnoDB")
            cur.execute("INSERT INTO inventarios VALUES (1,'inventario preservado')")
            cur.execute("INSERT INTO inventario_items VALUES (1,1,12.3456)")
            for table in PROTECTED_TABLES:
                if table not in {"inventarios", "inventario_items"}:
                    cur.execute(f"CREATE TABLE `{table}` (id BIGINT PRIMARY KEY, dato VARCHAR(30)) ENGINE=InnoDB")
                    cur.execute(f"INSERT INTO `{table}` VALUES (1,'registro preservado')")
            cur.execute("CREATE TABLE conciliaciones (id BIGINT PRIMARY KEY, dato VARCHAR(30)) ENGINE=InnoDB")
            cur.execute("INSERT INTO conciliaciones VALUES (1,'historial de prueba')")
            for table in LEGACY_TABLES:
                if table == "conciliaciones":
                    continue
                cur.execute(f"CREATE TABLE `{table}` (id BIGINT PRIMARY KEY, conciliacion_id BIGINT, FOREIGN KEY (conciliacion_id) REFERENCES conciliaciones(id)) ENGINE=InnoDB")
                cur.execute(f"INSERT INTO `{table}` VALUES (1,1)")
            cur.execute("ALTER TABLE conciliacion_remito_items ADD COLUMN item_id BIGINT, ADD FOREIGN KEY (item_id) REFERENCES conciliacion_items(id)")
            cur.execute("UPDATE conciliacion_remito_items SET item_id=1")
            cur.execute("CREATE TABLE analisis_stock (id BIGINT PRIMARY KEY, dato VARCHAR(30), conciliacion_legacy_id BIGINT NULL, CONSTRAINT nombre_fk_no_fijo FOREIGN KEY (conciliacion_legacy_id) REFERENCES conciliaciones(id)) ENGINE=InnoDB")
            cur.execute("INSERT INTO analisis_stock VALUES (1,'analisis preservado',1)")

    def tearDown(self):
        try:
            with self.db.cursor() as cur:
                cur.execute("SET FOREIGN_KEY_CHECKS=1")
                cur.execute(f"DROP DATABASE `{self.schema}`")
        finally:
            self.db.close()

    def snapshot(self):
        with self.db.cursor() as cur:
            cur.execute("SHOW FULL TABLES WHERE Table_type='BASE TABLE'")
            tables = [row[0] for row in cur.fetchall()]
            result = {}
            for table in tables:
                cur.execute(f"SELECT * FROM `{table}` ORDER BY 1")
                result[table] = cur.fetchall()
            return result

    def run_sql(self, apply=False, database=None, backup=True):
        script = SQL.replace("SET @invweb_e1_aplicar = 0;", f"SET @invweb_e1_aplicar = {int(apply)};")
        script = script.replace("'REEMPLAZAR_POR_BASE_DE_GESTION'", "'"+(database or self.schema)+"'")
        script = script.replace("SET @invweb_e1_respaldo_verificado = 0;", f"SET @invweb_e1_respaldo_verificado = {int(backup)};")
        output = []
        with self.db.cursor() as cur:
            for statement in statements(script):
                cur.execute(statement)
                while True:
                    if cur.description:
                        output.extend(cur.fetchall())
                    if not cur.nextset():
                        break
        return output

    def test_preview_preserves_every_record_and_table(self):
        before = self.snapshot()
        self.run_sql()
        self.assertEqual(self.snapshot(), before)

    def test_apply_preserves_full_inventory_rows_and_repeats_safely(self):
        before = self.snapshot()
        self.run_sql(apply=True)
        after = self.snapshot()
        self.assertFalse(set(LEGACY_TABLES) & set(after))
        for table in PROTECTED_TABLES:
            self.assertEqual(after[table], before[table])
        self.assertEqual(after['analisis_stock'], ((1,'analisis preservado',None),))
        self.run_sql(apply=True)
        self.assertEqual(self.snapshot(), after)

    def test_unexpected_foreign_key_aborts_before_any_data_change(self):
        with self.db.cursor() as cur:
            cur.execute("CREATE TABLE dependencia_no_prevista (id BIGINT PRIMARY KEY, ref BIGINT, FOREIGN KEY (ref) REFERENCES conciliaciones(id)) ENGINE=InnoDB")
            cur.execute("INSERT INTO dependencia_no_prevista VALUES (1,1)")
        before = self.snapshot()
        with self.assertRaises(pymysql.err.OperationalError) as caught:
            self.run_sql(apply=True)
        self.assertEqual(caught.exception.args[0], 1644)
        self.assertEqual(self.snapshot(), before)

    def test_wrong_database_name_aborts(self):
        before = self.snapshot()
        with self.assertRaises(pymysql.err.OperationalError):
            self.run_sql(apply=True, database='otra_base')
        self.assertEqual(self.snapshot(), before)

    def test_unconfirmed_backup_aborts(self):
        before = self.snapshot()
        with self.assertRaises(pymysql.err.OperationalError):
            self.run_sql(apply=True, backup=False)
        self.assertEqual(self.snapshot(), before)

    def test_disabled_foreign_key_checks_abort(self):
        before = self.snapshot()
        with self.db.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")
        with self.assertRaises(pymysql.err.OperationalError):
            self.run_sql(apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_optional_analysis_table_is_not_required(self):
        with self.db.cursor() as cur:
            cur.execute("DROP TABLE analisis_stock")
        before = self.snapshot()
        self.run_sql(apply=True)
        for table in PROTECTED_TABLES:
            self.assertEqual(self.snapshot()[table], before[table])

    def test_unknown_legacy_dependency_order_aborts(self):
        with self.db.cursor() as cur:
            cur.execute("ALTER TABLE conciliacion_items ADD COLUMN control_id BIGINT, ADD FOREIGN KEY (control_id) REFERENCES conciliacion_ingresos_control(id)")
        before = self.snapshot()
        with self.assertRaises(pymysql.err.OperationalError):
            self.run_sql(apply=True)
        self.assertEqual(self.snapshot(), before)
