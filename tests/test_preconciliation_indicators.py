import unittest
from pathlib import Path
from uuid import uuid4

from app.services.preconciliation_indicators import calcular_indicadores_preconciliacion
from app import preconciliation_audit as audit
from test_preconciliation_audit import calculate


class PreconciliationIndicatorTests(unittest.TestCase):
    def setUp(self):
        self.old_path = audit.STORE_PATH
        self.path = Path(__file__).resolve().parent / f"{uuid4().hex}.sqlite3"
        audit.STORE_PATH = self.path

    def tearDown(self):
        audit.STORE_PATH = self.old_path
        self.path.unlink(missing_ok=True)

    def test_quality_documentation_and_progress_percentages(self):
        calculation = calculate()
        notes = {
            "P1": {
                "causa": "MOV",
                "estado": "REVISAR_MOVIMIENTOS",
            }
        }
        result = calcular_indicadores_preconciliacion(calculation, notes)
        self.assertEqual(result["sistema"]["porcentaje"], 100)
        self.assertEqual(result["conciliacion_integral"]["porcentaje"], 0)
        self.assertEqual(result["consistencia_integral"]["porcentaje"], 0)
        self.assertEqual(result["cobertura_causas"]["porcentaje"], 50)
        self.assertEqual(result["avance_analisis"]["porcentaje"], 50)
        self.assertEqual(len(result["escenarios"]), 3)
        self.assertEqual(result["peor_escenario"]["porcentaje"], 0)

    def test_empty_denominator_is_reported_as_not_applicable(self):
        result = calcular_indicadores_preconciliacion({"escenarios": [], "movimientos": []})
        self.assertIsNone(result["sistema"]["porcentaje"])
        self.assertIsNone(result["auditoria_documental"]["porcentaje"])

    def test_adjustments_are_incidence_evidence_not_an_explanation_ratio(self):
        calculation = calculate()
        calculation["escenarios"][0]["filas"][0]["sistema_ok"] = False
        calculation["escenarios"][0]["filas"][0]["ajustes_sistema"] = [{"cantidad": 5}]
        result = calcular_indicadores_preconciliacion(calculation)
        self.assertIn("diferencias_con_ajustes", result)
        self.assertNotIn("ajustes_explicativos", result)


if __name__ == "__main__":
    unittest.main()
