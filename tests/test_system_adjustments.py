from datetime import date, datetime
from unittest.mock import patch
import unittest

from app.services.system_adjustments import obtener_ajustes_sistema, resumen_ajustes


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, _query, parameters):
        self.parameters = parameters
        return _Result(self.rows)


class _Engine:
    def __init__(self, rows):
        self.connection = _Connection(rows)

    def connect(self):
        return self.connection


class SystemAdjustmentTests(unittest.TestCase):
    def test_reads_pt_and_process_adjustments_without_changing_their_sign(self):
        engine = _Engine([
            {"codigo": " P1 ", "operacion": "999.0", "cantidad": -12, "fecha": datetime(2026, 8, 10, 8), "motivo": "AJUSTE INV"},
            {"codigo": "P1", "operacion": "020", "cantidad": 5, "fecha": date(2026, 8, 11), "motivo": "PROCESO"},
        ])
        with patch("app.services.system_adjustments.production_engine", engine):
            result = obtener_ajustes_sistema({"p1"}, "2026-08-01", "2026-08-31")
        self.assertEqual(result["P1"][0]["etapa"], "TERMINADO")
        self.assertEqual(result["P1"][1]["etapa"], "PROCESO")
        self.assertEqual(resumen_ajustes(result["P1"]), {
            "cantidad": 2,
            "neto": -7,
            "magnitud": 17,
            "producto_terminado": -12,
            "en_proceso": 5,
        })
        self.assertEqual(engine.connection.parameters["fecha_desde"], date(2026, 8, 2))
        self.assertEqual(engine.connection.parameters["fecha_hasta"], date(2026, 9, 1))


if __name__ == "__main__":
    unittest.main()
