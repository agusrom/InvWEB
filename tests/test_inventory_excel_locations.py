from pathlib import Path
from types import SimpleNamespace
import unittest

from app.services.count_locations import (
    desglosar_conteo_por_ubicacion,
    ubicacion_de_registro,
)


ROOT = Path(__file__).resolve().parents[1]


class InventoryExcelLocationTests(unittest.TestCase):
    def test_location_is_read_from_mobile_record_prefix(self):
        self.assertEqual(ubicacion_de_registro("[DISPONIBLE] Dársena 2"), "DISPONIBLE")
        self.assertEqual(ubicacion_de_registro("[linea] Soldadura"), "LINEA")
        self.assertEqual(ubicacion_de_registro("[SCRAP]"), "SCRAP")
        self.assertEqual(ubicacion_de_registro("Carga anterior"), "SIN_UBICACION")

    def test_breakdown_reconciles_with_physical_total(self):
        items = [
            SimpleNamespace(id=1, conteo_fisico=40),
            SimpleNamespace(id=2, conteo_fisico=0),
            SimpleNamespace(id=3, conteo_fisico=None),
        ]
        cajas = [
            {"item_id": 1, "cantidad": 10, "observacion": "[DISPONIBLE]"},
            {"item_id": 1, "cantidad": 8, "observacion": "[LINEA]"},
            {"item_id": 1, "cantidad": 2, "observacion": "[SCRAP]"},
            {"item_id": 1, "cantidad": 5, "observacion": "Registro viejo"},
            {"item_id": 99, "cantidad": 100, "observacion": "[LINEA]"},
        ]

        result = desglosar_conteo_por_ubicacion(items, cajas)

        self.assertEqual(result[1]["DISPONIBLE"], 10)
        self.assertEqual(result[1]["LINEA"], 8)
        self.assertEqual(result[1]["SCRAP"], 2)
        self.assertEqual(result[1]["SIN_UBICACION"], 20)
        self.assertEqual(sum(result[1].values()), 40)
        self.assertTrue(all(value == 0 for value in result[2].values()))
        self.assertTrue(all(value is None for value in result[3].values()))

    def test_inventory_export_exposes_location_columns(self):
        excel_source = (ROOT / "app/services/excel.py").read_text(encoding="utf-8")
        api_source = (ROOT / "app/routers/api.py").read_text(encoding="utf-8")
        for header in (
            '"Disponible"',
            '"En línea"',
            '"Scrap"',
            '"Sin ubicación / ajuste PC"',
        ):
            self.assertIn(header, excel_source)
        self.assertIn("generar_excel(inventario, listar_cajas(inventario_id))", api_source)


if __name__ == "__main__":
    unittest.main()
