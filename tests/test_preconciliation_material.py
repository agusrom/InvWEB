"""Conversión de materia prima a piezas comparables sin acceder a MySQL."""
import os
from types import SimpleNamespace
from unittest.mock import patch
import unittest

os.environ.setdefault("DATABASE_URL", "mysql+pymysql://test:test@127.0.0.1/test")

from app.routers.api import (  # noqa: E402
    agrupar_filas_material_compartido,
    completar_codigos_cliente_preconciliacion,
    conteo_explotado_grupos_material_compartido,
    conteo_directo_por_codigo,
    detalle_conteo_fisico_por_codigo,
    detalle_stock_sistema_por_codigo,
    stock_sistema_por_codigo,
)


class MaterialComparableTests(unittest.TestCase):
    def test_shared_material_initial_count_is_used_once_per_lot(self):
        inventory = SimpleNamespace(items=[
            SimpleNamespace(id=1, codigo="P1", codigo_material="MP-1", lote="10001", etapa="MATERIAL", stock_sistema=100, conteo_fisico=80),
            SimpleNamespace(id=2, codigo="P2", codigo_material="MP-1", lote="10001", etapa="MATERIAL", stock_sistema=0, conteo_fisico=80),
            SimpleNamespace(id=3, codigo="P1", codigo_material="MP-1", lote="", etapa="PROCESO_GLOBAL", stock_sistema=0, conteo_fisico=10),
            SimpleNamespace(id=4, codigo="P2", codigo_material="MP-1", lote="", etapa="TERMINADO", stock_sistema=0, conteo_fisico=20),
        ])
        piece = SimpleNamespace(consumo_material=2, unidad_consumo="C/U")
        with patch("app.routers.api.buscar_pieza", return_value=piece):
            totals = conteo_explotado_grupos_material_compartido(
                inventory,
                {"MP-1": ["P1", "P2"]},
            )
        self.assertEqual(totals["MP-1"], 70)

    def test_shared_material_rows_use_one_joint_equation(self):
        income = {
            "remito": "100",
            "fecha": "2026-09-01",
            "codigo_material": "MP-1",
            "cantidad": 5,
        }
        detail = {
            "materia_prima": 0,
            "materia_prima_equivalente": 0,
            "en_proceso": 0,
            "producto_terminado": 0,
            "stock_asignado": 0,
            "consumo_material": 1,
            "unidad_consumo": "C/U",
        }
        rows = []
        for code, initial, outcome, current in (
            ("P1", 10, 2, 14),
            ("P2", 20, 3, 16),
        ):
            rows.append({
                "codigo": code,
                "fisico_inicial": initial,
                "detalle_ingresos": [dict(income, codigo=code)],
                "detalle_egresos": [{"pieza_origen": code, "cantidad_equivalente": outcome}],
                "ingresos": 5,
                "egresos": outcome,
                "detalle_sistema": dict(detail, producto_terminado=current),
                "detalle_fisico": dict(detail, producto_terminado=current),
                "conteo_explotado_actual": current,
                "ajustes_sistema": [],
            })
        grouped = agrupar_filas_material_compartido(
            rows,
            {"MP-1": ["P1", "P2"]},
            5,
        )
        self.assertEqual(len(grouped), 1)
        row = grouped[0]
        self.assertEqual(row["codigo"], "MP:MP-1")
        self.assertEqual(row["codigos"], ["P1", "P2"])
        self.assertEqual(row["fisico_inicial"], 30)
        self.assertEqual(row["ingresos"], 5)
        self.assertEqual(row["egresos"], 5)
        self.assertEqual(row["esperado"], 30)
        self.assertEqual(row["conteo_explotado_actual"], 30)
        self.assertTrue(row["conciliacion_ok"])
        self.assertEqual(
            [piece["codigo"] for piece in row["detalle_piezas"]],
            ["P1", "P2"],
        )
        self.assertFalse(row["sistema_ok"])

    def test_old_analysis_is_enriched_with_customer_codes_before_export(self):
        calculation = {
            "escenarios": [{"filas": [{
                "codigo": "COMP-1",
                "detalle_ingresos": [{"codigo_material": "MP-1"}],
                "detalle_egresos": [{"pieza_origen": "PADRE-1"}],
            }]}],
            "movimientos": [
                {"codigo": "MP-1"},
                {"codigo": "PADRE-1"},
            ],
        }
        customer_codes = {"COMP-1": "CLI-COMP", "PADRE-1": "CLI-PADRE"}
        with patch(
            "app.routers.api.buscar_codigos_cliente_piezas",
            return_value=customer_codes,
        ):
            completar_codigos_cliente_preconciliacion(calculation)
        row = calculation["escenarios"][0]["filas"][0]
        self.assertEqual(row["codigo_cliente"], "CLI-COMP")
        self.assertEqual(row["detalle_egresos"][0]["codigo_cliente_origen"], "CLI-PADRE")
        self.assertEqual(calculation["movimientos"][1]["codigo_cliente"], "CLI-PADRE")
        self.assertEqual(calculation["movimientos"][0]["codigo_cliente"], "")

    def test_material_is_divided_by_consumption_and_added_to_totals(self):
        inventory = SimpleNamespace(items=[
            SimpleNamespace(codigo="P1", etapa="MATERIAL", stock_sistema=40, conteo_fisico=30, stock_asignado=0),
            SimpleNamespace(codigo="P1", etapa="PROCESO_GLOBAL", stock_sistema=5, conteo_fisico=6, stock_asignado=0),
            SimpleNamespace(codigo="P1", etapa="TERMINADO", stock_sistema=7, conteo_fisico=8, stock_asignado=0),
        ])
        piece = SimpleNamespace(consumo_material=2, unidad_consumo="C/U")
        with patch("app.routers.api.buscar_pieza", return_value=piece):
            self.assertEqual(stock_sistema_por_codigo(inventory)["P1"], 32)
            self.assertEqual(conteo_directo_por_codigo(inventory)["P1"], 29)
            detail = detalle_conteo_fisico_por_codigo(inventory)["P1"]
            system_detail = detalle_stock_sistema_por_codigo(inventory)["P1"]
        self.assertEqual(detail["materia_prima"], 30)
        self.assertEqual(detail["materia_prima_equivalente"], 15)
        self.assertEqual(detail["total_productivo"], 29)
        self.assertEqual(detail["total_general"], 29)
        self.assertEqual(system_detail["total_general"], 32)
        self.assertEqual(
            detail["total_general"],
            detail["materia_prima_equivalente"]
            + detail["en_proceso"]
            + detail["producto_terminado"],
        )
        self.assertEqual(detail["unidad_consumo"], "C/U")


if __name__ == "__main__":
    unittest.main()
