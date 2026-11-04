from pathlib import Path
import unittest

from app.routers.api import filtrar_componentes_inventario


ROOT = Path(__file__).resolve().parents[1]


class ErgonomicInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desktop = (ROOT / "app/static/js/app.js").read_text(encoding="utf-8")
        cls.mobile = (ROOT / "app/static/js/mobile_count.js").read_text(encoding="utf-8")
        cls.api = (ROOT / "app/routers/api.py").read_text(encoding="utf-8")
        cls.schemas = (ROOT / "app/schemas.py").read_text(encoding="utf-8")
        cls.aux = (ROOT / "app/inventory_aux_store.py").read_text(encoding="utf-8")
        cls.editor = (ROOT / "app/static/js/template_editor.js").read_text(encoding="utf-8")

    def test_pc_totals_are_derived_from_records(self):
        self.assertIn("count-total-display", self.desktop)
        self.assertNotIn('class="conteo-input ', self.desktop)
        self.assertIn("Fuente única del físico", (ROOT / "app/local_count_store.py").read_text(encoding="utf-8"))

    def test_zero_is_an_auditable_record_on_both_clients(self):
        self.assertIn('tipo_registro: "CONFIRMACION_CERO"', self.desktop)
        self.assertIn('tipo_registro: "CONFIRMACION_CERO"', self.mobile)

    def test_templates_can_mix_and_merge_items(self):
        self.assertIn("plantilla_ids", self.schemas)
        self.assertIn("tipo_articulo", self.schemas)
        self.assertIn("currentItemType", self.editor)
        self.assertIn("items_plantilla_combinados", self.api)

    def test_new_metadata_is_sqlite_only(self):
        self.assertIn("inventarios_auxiliares.db", self.aux)
        self.assertIn("plantilla_item_tipos", self.aux)
        self.assertIn("inventario_plantillas", self.aux)
        self.assertIn("conteo_registro_meta", self.aux)

    def test_executive_and_component_views_exist(self):
        self.assertIn("renderResumenEjecutivo", self.desktop)
        self.assertIn("cargarComponentesInventario", self.desktop)
        self.assertIn('@router.get("/inventarios/{inventario_id}/componentes")', self.api)
        self.assertIn('@router.get("/inventarios/{inventario_id}/resumen-ejecutivo")', self.api)

    def test_component_explosion_is_filtered_only_after_full_calculation(self):
        explotados = [
            {"codigo": "HIJO", "uso": 6.0},
            {"codigo": "TERMINAL", "uso": 8.0},
            {"codigo": "FUERA", "uso": 4.0},
        ]
        resultado = filtrar_componentes_inventario(
            explotados, {"PADRE", "HIJO", "TERMINAL"},
        )
        self.assertEqual(resultado, [
            {"codigo": "HIJO", "uso": 6.0},
            {"codigo": "TERMINAL", "uso": 8.0},
        ])


if __name__ == "__main__":
    unittest.main()
