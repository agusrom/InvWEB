from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InventoryDiffusionUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = (
            ROOT / "app/templates/inventory_diffusion.html"
        ).read_text(encoding="utf-8")
        cls.script = (
            ROOT / "app/static/js/inventory_diffusion.js"
        ).read_text(encoding="utf-8")
        cls.main = (ROOT / "app/main.py").read_text(encoding="utf-8")

    def test_general_reliability_reuses_the_pc_metric(self):
        self.assertIn("inventory.confiabilidad", self.script)
        self.assertIn("inventory.items_evaluables", self.script)
        self.assertIn("inventory.items_evaluados", self.script)
        self.assertIn("inventory.items_ok", self.script)
        self.assertNotIn(
            "const reliability = rows.length ? correct * 100 / rows.length",
            self.script,
        )

    def test_report_receives_configured_tolerance_and_target(self):
        self.assertIn('id="settings-data"', self.template)
        self.assertIn('"configuracion": cargar_configuracion(db)', self.main)
        self.assertIn("settings.tolerancia_pct", self.script)
        self.assertIn("settings.objetivo_confiabilidad_pct", self.script)
        self.assertNotIn("const tolerance = 5;", self.script)


if __name__ == "__main__":
    unittest.main()
