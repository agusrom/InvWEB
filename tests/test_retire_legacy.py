"""El retiro nunca debe planificar borrados de inventarios ni análisis activos."""
import unittest
from scripts.retirar_modulos_prueba import build_plan, LEGACY_TABLES


def fk(table, referenced, column="id", schema="gestion"):
    return dict(table_schema=schema, table_name=table, column_name=column,
                referenced_schema="gestion", referenced_table=referenced,
                constraint_name=f"fk_{table}_{referenced}")


class RetireLegacyTests(unittest.TestCase):
    def test_children_are_dropped_first_and_inventories_are_preserved(self):
        tables = set(LEGACY_TABLES) | {"inventarios", "inventario_items"}
        plan = build_plan("gestion", tables, [fk("conciliacion_items", "conciliaciones")])
        self.assertLess(plan.index("DROP TABLE `conciliacion_items`"), plan.index("DROP TABLE `conciliaciones`"))
        self.assertEqual({sql.split('`')[1] for sql in plan}, set(LEGACY_TABLES))

    def test_active_analyses_are_unlinked_without_deleting_them(self):
        plan = build_plan("gestion", {"conciliaciones", "analisis_stock"},
                          [fk("analisis_stock", "conciliaciones", "conciliacion_legacy_id")])
        self.assertTrue(plan[0].startswith("UPDATE `analisis_stock`"))
        self.assertTrue(plan[1].startswith("ALTER TABLE `analisis_stock` DROP FOREIGN KEY"))
        self.assertEqual(plan[-1], "DROP TABLE `conciliaciones`")

    def test_unexpected_dependencies_block_all_cleanup(self):
        for dependency in [fk("inventarios", "conciliaciones"), fk("externa", "conciliaciones", schema="otra"), fk("analisis_stock", "conciliaciones", "otro_campo")]:
            with self.subTest(dependency=dependency), self.assertRaises(RuntimeError):
                build_plan("gestion", {"conciliaciones"}, [dependency])

    def test_repeating_cleanup_has_no_actions(self):
        self.assertEqual(build_plan("gestion", {"inventarios", "inventario_items"}, []), [])

    def test_circular_dependencies_are_not_bypassed(self):
        with self.assertRaises(RuntimeError):
            build_plan("gestion", {"conciliaciones", "conciliacion_items"},
                       [fk("conciliaciones", "conciliacion_items"), fk("conciliacion_items", "conciliaciones")])

    def test_runtime_keeps_inventory_and_analysis_routes_without_legacy_models(self):
        import os
        os.environ.setdefault("DATABASE_URL", "mysql+pymysql://test:test@127.0.0.1/test")
        from app.main import app
        from app.database import Base
        from app.schema_validation import TABLAS_AUXILIARES
        paths = {route.path for route in app.routes}
        self.assertIn("/analisis-stock", paths)
        self.assertIn("/api/inventarios/{inventario_id}/componentes", paths)
        self.assertIn("/api/inventarios/{inventario_id}/conteo-movil/cajas", paths)
        self.assertIn("/api/notas-cronograma", paths)
        self.assertFalse(any("/conciliaciones" in path or "/deposito" in path for path in paths))
        self.assertNotIn("conciliaciones", Base.metadata.tables)
        self.assertIn("inventarios", Base.metadata.tables)
        self.assertFalse(set(LEGACY_TABLES) & TABLAS_AUXILIARES)
