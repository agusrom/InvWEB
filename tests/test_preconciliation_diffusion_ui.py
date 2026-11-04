from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PreconciliationDiffusionUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = (
            ROOT / "app/templates/preconciliation_diffusion.html"
        ).read_text(encoding="utf-8")
        cls.script = (
            ROOT / "app/static/js/preconciliation_diffusion.js"
        ).read_text(encoding="utf-8")
        cls.analysis_template = (
            ROOT / "app/templates/preconciliation.html"
        ).read_text(encoding="utf-8")
        cls.analysis_script = (
            ROOT / "app/static/js/preconciliation.js"
        ).read_text(encoding="utf-8")
        cls.main = (ROOT / "app/main.py").read_text(encoding="utf-8")

    def test_saved_analysis_has_a_dedicated_diffusion_action(self):
        self.assertIn('id="conciliation-diffusion"', self.analysis_template)
        self.assertIn("function openConciliationDiffusion()", self.analysis_script)
        self.assertIn("if (!state.analysisId)", self.analysis_script)
        self.assertIn("/preconciliacion/difusion?", self.analysis_script)

    def test_printable_summary_contains_the_complete_formula(self):
        self.assertIn("DIFUSIÓN DE RESULTADOS DE CONCILIACIÓN", self.template)
        self.assertIn("<th>Inicial</th><th>Ingresos</th><th>Egresos</th><th>Scrap</th>", self.template)
        self.assertIn("<th>Esperado</th><th>Conteo actual</th><th>Diferencia</th><th>Desvío</th>", self.template)
        self.assertIn("row.diferencia_conciliacion", self.script)
        self.assertIn("row.porcentaje_desvio_conciliacion", self.script)

    def test_second_page_prioritizes_causes_comments_and_documentation(self):
        self.assertIn('id="critical-list"', self.template)
        self.assertIn('id="cause-chart"', self.template)
        self.assertIn('id="audit-chart"', self.template)
        self.assertIn('id="direction-chart"', self.template)
        self.assertIn("commentFor(row)", self.script)
        self.assertIn("if (code) causeCounts.set", self.script)
        self.assertIn("movement.verificado", self.script)

    def test_route_validates_analysis_inventory_and_scenario(self):
        self.assertIn('"/inventarios/{inventario_id}/preconciliacion/difusion"', self.main)
        self.assertIn('guardado["final_id"]', self.main)
        self.assertIn("El escenario inicial no pertenece", self.main)


if __name__ == "__main__":
    unittest.main()
