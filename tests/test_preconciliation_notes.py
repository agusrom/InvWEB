from pathlib import Path
from uuid import uuid4
import unittest

from app import preconciliation_store as store


class PreconciliationNotesTests(unittest.TestCase):
    def setUp(self):
        self.old_path = store.STORE_PATH
        self.path = Path(__file__).resolve().parent / f"{uuid4().hex}.json"
        store.STORE_PATH = self.path

    def tearDown(self):
        store.STORE_PATH = self.old_path
        self.path.unlink(missing_ok=True)
        self.path.with_suffix(".tmp").unlink(missing_ok=True)

    def test_validation_checklist_is_saved_with_the_piece_note(self):
        saved = store.guardar_nota(
            7,
            " p1 ",
            "MOV",
            "Controlado",
            "REVISAR_MOVIMIENTOS",
            {"conteo": True, "egresos": True, "campo_invalido": True},
        )
        self.assertEqual(saved["controles"], {"conteo": True, "egresos": True})
        self.assertEqual(store.notas_inventario(7)["P1"]["observacion"], "Controlado")


if __name__ == "__main__":
    unittest.main()
