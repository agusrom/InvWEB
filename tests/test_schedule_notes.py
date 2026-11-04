"""Persistencia y validación de notas independientes del inventario."""
from datetime import date
import unittest
from fastapi import HTTPException
from pydantic import ValidationError
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pathlib import Path
from app import schedule_notes_store as store
from app.routers.notes import crear_nota, actualizar_nota, eliminar_nota
from app.schemas import NotaCronogramaEntrada


class ScheduleNotesTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "notes.db"
        self.patcher = patch.object(store, "STORE_PATH", self.path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_create_edit_close_and_reopen_survive_new_connection(self):
        data = NotaCronogramaEntrada(fecha=date(2026, 11, 4), titulo="  Preparar depósito  ", contenido="Separar cajas\nImprimir planillas")
        saved = crear_nota(data)
        self.assertEqual(saved["titulo"], "Preparar depósito")
        self.assertFalse(saved["cerrada"])
        note_id = saved["id"]
        changed = data.model_copy(update={"cerrada": True, "fecha": date(2026, 11, 5), "contenido": "Preparación terminada"})
        actualizar_nota(note_id, changed)
        persisted = store.listar_notas()[0]
        self.assertTrue(persisted["cerrada"])
        self.assertEqual(persisted["fecha"], "2026-11-05")
        self.assertEqual(persisted["contenido"], "Preparación terminada")
        reopened = actualizar_nota(note_id, changed.model_copy(update={"cerrada": False}))
        self.assertFalse(reopened["cerrada"])
        self.assertEqual(len(store.listar_notas()), 1)

    def test_unknown_note_is_404(self):
        with self.assertRaises(HTTPException) as caught:
            actualizar_nota(999, NotaCronogramaEntrada(fecha=date.today(), titulo="Nota"))
        self.assertEqual(caught.exception.status_code, 404)

    def test_blank_title_is_rejected_without_saving(self):
        with self.assertRaises(HTTPException) as caught:
            crear_nota(NotaCronogramaEntrada(fecha=date.today(), titulo="   "))
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(store.listar_notas(), [])

    def test_invalid_dates_and_excessive_text_are_rejected(self):
        for values in [dict(fecha="2026-02-30", titulo="Nota"), dict(fecha="2026-11-04", titulo="x"*151), dict(fecha="2026-11-04", titulo="Nota", contenido="x"*15001)]:
            with self.subTest(values=list(values)):
                with self.assertRaises(ValidationError):
                    NotaCronogramaEntrada(**values)

    def test_delete_closed_note_persists_and_keeps_other_notes(self):
        first = crear_nota(NotaCronogramaEntrada(fecha=date.today(), titulo="Eliminar", cerrada=True))
        other = crear_nota(NotaCronogramaEntrada(fecha=date.today(), titulo="Conservar"))
        response = eliminar_nota(first["id"])
        self.assertEqual(response.status_code, 204)
        self.assertEqual(store.listar_notas(), [other])
        with self.assertRaises(HTTPException) as caught:
            actualizar_nota(first["id"], NotaCronogramaEntrada(fecha=date.today(), titulo="No recrear"))
        self.assertEqual(caught.exception.status_code, 404)

    def test_delete_unknown_note_is_404(self):
        with self.assertRaises(HTTPException) as caught:
            eliminar_nota(999)
        self.assertEqual(caught.exception.status_code, 404)
