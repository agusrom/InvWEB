"""Remitos manuales completos, persistencia atómica y explosión sin MySQL real."""
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from pydantic import ValidationError

from tests import test_open_stock_analysis as stock_tests
from app import preconciliation_audit as audit
from app.models import InventarioItem
from app.routers import api
from app.schemas import PreconciliacionManualRemitoEntrada, PreconciliacionCalculoEntrada
from app.services.piece_provider import _recorrer_estructura


class ManualRemittanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = stock_tests.OpenStockAnalysisTests()
        self.fixture.setUp()
        self.db = self.fixture.db
        self.final = self.fixture.final
        self.initial = self.fixture.initial
        self.final.items[0].conteo_fisico = 10
        self.initial.items.append(InventarioItem(codigo='ALT', descripcion='Otra', etapa='TERMINADO', conteo_fisico=20))
        self.final.items.append(InventarioItem(codigo='ALT', descripcion='Otra', etapa='TERMINADO', conteo_fisico=20))
        self.db.commit()

    def tearDown(self):
        self.fixture.tearDown()

    def payload(self, **changes):
        data = dict(tipo='IN', fecha='2026-11-03', remito='R-100', observacion='Entrega conjunta',
                    solicitud_id='solicitud-1', renglones=[dict(codigo='MP1', cantidad=5), dict(codigo='MP2', cantidad=7)])
        data.update(changes)
        return data

    def save(self, data=None):
        entry = PreconciliacionManualRemitoEntrada.model_validate(data or self.payload())
        return api.agregar_remito_manual_preconciliacion(self.final.id, entry, self.db)

    def stored(self):
        with audit.connection() as db:
            return audit.read(db, self.final.id)['movimientos']

    def calculate(self):
        result = api.calcular_preconciliacion(self.final.id,
            PreconciliacionCalculoEntrada(inventarios_iniciales=[self.initial.id]), self.db)
        return result, {row['codigo']: row for row in result['escenarios'][0]['filas']}

    def test_multiple_materials_share_header_and_add_to_corresponding_components(self):
        saved = self.save()
        self.assertEqual(len(saved['claves']), 2)
        records = list(self.stored().values())
        self.assertEqual({r['remito'] for r in records}, {'R-100'})
        self.assertEqual({r['fecha'] for r in records}, {'2026-11-03'})
        self.assertEqual({r['observacion'] for r in records}, {'Entrega conjunta'})
        with patch.object(api, '_materiales_por_pieza', return_value={'MP1': {'TEST'}, 'MP2': {'ALT'}}):
            _, rows = self.calculate()
        self.assertEqual(rows['TEST']['ingresos'], 5)
        self.assertEqual(rows['ALT']['ingresos'], 7)
        self.assertEqual(rows['TEST']['esperado'], 15)
        self.assertEqual(rows['ALT']['esperado'], 27)

    def test_finished_products_explode_recursively_only_into_analysis_components(self):
        tree = {'PT1': [('SUB', 2), ('AJENA', 9)], 'SUB': [('TEST', 3)], 'PT2': [('TEST', 1), ('ALT', 4)]}
        structure = lambda code: _recorrer_estructura(code, lambda c: tree.get(c, []), 20)
        self.save(self.payload(tipo='OUT', renglones=[dict(codigo='PT1', cantidad=2), dict(codigo='PT2', cantidad=3)]))
        with patch('app.services.movements.obtener_estructura_recursiva', side_effect=structure):
            result, rows = self.calculate()
        self.assertEqual(set(rows), {'TEST', 'ALT'})
        self.assertEqual(rows['TEST']['egresos'], 15)  # 2 PT1 x6 + 3 PT2 x1
        self.assertEqual(rows['ALT']['egresos'], 12)   # 3 PT2 x4
        self.assertEqual({r['pieza_origen'] for r in rows['TEST']['detalle_egresos']}, {'PT1', 'PT2'})
        self.assertEqual(len(result['movimientos']), 2)
        self.assertEqual({m['codigo'] for m in result['movimientos']}, {'PT1', 'PT2'})

    def test_retry_returns_same_keys_without_duplicating_remittance(self):
        first = self.save()
        second = self.save()
        self.assertEqual(first['claves'], second['claves'])
        self.assertTrue(second['reutilizado'])
        self.assertEqual(len(self.stored()), 2)
        changed = self.payload()
        changed['renglones'][0]['cantidad'] = 999
        with self.assertRaises(HTTPException):
            self.save(changed)
        self.assertEqual(len(self.stored()), 2)

    def test_invalid_or_repeated_codes_reject_whole_remittance(self):
        for code in (' ', ' mp1 '):
            with self.subTest(code=code):
                data = self.payload(renglones=[dict(codigo='MP1', cantidad=5), dict(codigo=code, cantidad=7)])
                with self.assertRaises(HTTPException):
                    self.save(data)
                self.assertEqual(self.stored(), {})
        for quantity in (0, -1, float('nan'), float('inf')):
            with self.subTest(quantity=quantity):
                with self.assertRaises(ValidationError):
                    self.save(self.payload(renglones=[dict(codigo='MP1', cantidad=5), dict(codigo='MP2', cantidad=quantity)]))
                self.assertEqual(self.stored(), {})

    def test_date_limits_and_batch_size_are_validated_before_writes(self):
        with self.assertRaises(HTTPException):
            self.save(self.payload(fecha='2026-11-06'))
        for rows in ([], [dict(codigo=f'C{i}', cantidad=1) for i in range(201)]):
            with self.assertRaises(ValidationError):
                self.save(self.payload(renglones=rows))
        self.assertEqual(self.stored(), {})

    def test_storage_failure_rolls_back_whole_remittance(self):
        with patch.object(audit, 'write', side_effect=RuntimeError('Falló SQLite')):
            with self.assertRaises(RuntimeError):
                self.save()
        self.assertEqual(self.stored(), {})

    def test_components_and_periods_outside_analysis_do_not_affect_totals(self):
        self.save(self.payload(tipo='OUT', renglones=[dict(codigo='TEST', cantidad=2), dict(codigo='AJENA', cantidad=50)]))
        result, rows = self.calculate()
        self.assertEqual(rows['TEST']['egresos'], 2)
        self.assertEqual(rows['ALT']['egresos'], 0)
        self.assertNotIn('AJENA', rows)
        self.assertTrue(any('AJENA' in warning for warning in result['escenarios'][0]['advertencias']))
        # Fecha inicial incluida: se respeta la incorporación manual al período.
        self.save(self.payload(fecha=self.initial.fecha.isoformat(), solicitud_id='solicitud-2'))
        with patch.object(api, '_materiales_por_pieza', return_value={'MP1': {'TEST'}, 'MP2': {'ALT'}}):
            _, rows = self.calculate()
        self.assertEqual(rows['TEST']['ingresos'], 5)
        self.assertEqual(rows['ALT']['ingresos'], 7)
