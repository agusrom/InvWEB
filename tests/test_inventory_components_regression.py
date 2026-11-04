"""Protege la explosión de v1.16 al integrar notas en la portada."""
import os
from types import SimpleNamespace
from unittest.mock import patch
import unittest

os.environ.setdefault("DATABASE_URL", "mysql+pymysql://test:test@127.0.0.1/test")
from app.routers.api import componentes_inventario
from app.services.piece_provider import _recorrer_estructura


def item(codigo, sistema, fisico, etapa="TERMINADO", **extra):
    return SimpleNamespace(codigo=codigo, stock_sistema=sistema, conteo_fisico=fisico,
                           etapa=etapa, descripcion=codigo, unidad="u", **extra)


class InventoryComponentsRegressionTests(unittest.TestCase):
    def calculate(self, items):
        # PADRE -> SUBCONJUNTO x2 -> HIJO x3: each parent embeds six children.
        # FUERA is terminal but absent from the inventory and must stay hidden.
        tree = {"PADRE": [("SUBCONJUNTO", 2), ("FUERA", 4)],
                "SUBCONJUNTO": [("HIJO", 3)]}
        def structure(codigo):
            return _recorrer_estructura(codigo, lambda c: tree.get(c, []), 20)
        with patch("app.routers.api.buscar_inventario", return_value=SimpleNamespace(id=7, items=items)), \
             patch("app.services.movements.obtener_estructura_recursiva", side_effect=structure):
            result = componentes_inventario(7, db=None)
        self.assertEqual(result["inventario_id"], 7)
        return {row["codigo"]: row for row in result["componentes"]}

    def test_full_depth_and_direct_embedded_totals_stay_in_same_inventory(self):
        rows = self.calculate([item("PADRE", 10, 8), item("HIJO", 5, 4)])
        self.assertEqual(set(rows), {"HIJO"})
        child = rows["HIJO"]
        self.assertEqual(child["sistema_directo"], 5)
        self.assertEqual(child["sistema_embebido"], 60)
        self.assertEqual(child["sistema_total"], 65)
        self.assertEqual(child["fisico_total"], 52)
        self.assertEqual(child["diferencia"], -13)
        self.assertEqual(child["detalle"][0]["uso"], 6)

    def test_pending_parent_keeps_equivalent_count_incomplete(self):
        child = self.calculate([item("PADRE", 10, None), item("HIJO", 5, 4)])["HIJO"]
        self.assertFalse(child["completo"])
        self.assertIsNone(child["fisico_total"])
        self.assertIsNone(child["diferencia"])

    def test_shared_material_is_counted_once_per_lot(self):
        rows = self.calculate([
            item("PADRE", 100, 80, "MATERIAL", codigo_material="MP", lote="L1"),
            item("HIJO", 0, 80, "MATERIAL", codigo_material="MP", lote="L1"),
            item("HIJO", 20, 15, "MATERIAL", codigo_material="MP", lote="L2"),
        ])
        self.assertEqual(rows["MP"]["sistema_total"], 120)
        self.assertEqual(rows["MP"]["fisico_total"], 95)
        self.assertEqual(len(rows["MP"]["detalle"]), 2)
