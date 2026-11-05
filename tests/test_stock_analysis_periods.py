"""Comparaciones acumuladas y consecutivas sin datos ni conexiones reales."""
from copy import deepcopy
from datetime import date, datetime
import unittest
from unittest.mock import patch
from openpyxl import load_workbook

from tests import test_open_stock_analysis as fixtures
from app import preconciliation_audit as audit
from app.models import Inventario, InventarioItem
from app.routers import api
from app.schemas import PreconciliacionCalculoEntrada, PreconciliacionGuardarEntrada
from app.services.preconciliation_excel import crear_excel_preconciliacion
from app.services.preconciliation_indicators import calcular_indicadores_preconciliacion
from app.services.stock_analysis_comparison import construir_periodos_consecutivos


class StockAnalysisPeriodsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.OpenStockAnalysisTests()
        self.fixture.setUp()
        self.db, self.initial, self.final = self.fixture.db, self.fixture.initial, self.fixture.final
        self.middle = Inventario(codigo='MIDDLE', cliente='Cliente', fecha=date(2026, 11, 3), responsable='Test', estado='Cerrado',
            items=[InventarioItem(codigo='TEST', descripcion='Pieza', etapa='TERMINADO', stock_sistema=14, conteo_fisico=14)])
        self.final.items[0].conteo_fisico = 18
        self.final.items[0].stock_sistema = 18
        self.db.add(self.middle)
        self.db.commit()
        self.patch = patch.object(api, 'calcular_movimientos', side_effect=self.movements)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.fixture.tearDown()

    def movements(self, *args, **kwargs):
        early = kwargs['fecha_inicial'] == self.initial.fecha
        incomes = [dict(codigo='TEST', codigo_material='MP', fecha='2026-11-04', remito='IN2', cantidad=5)]
        outcomes = [dict(pieza_origen='TEST', fecha='2026-11-04', remito='OUT2', cantidad_pieza=1, uso=1, cantidad_equivalente=1)]
        if early:
            incomes.append(dict(codigo='TEST', codigo_material='MP', fecha='2026-11-02', remito='IN1', cantidad=5))
            outcomes.append(dict(pieza_origen='TEST', fecha='2026-11-02', remito='OUT1', cantidad_pieza=1, uso=1, cantidad_equivalente=1))
        return dict(ingresos_por_codigo={'TEST': 10 if early else 5}, egresos_por_codigo={'TEST': 2 if early else 1},
            detalles_ingreso={'TEST': incomes}, detalles_egreso={'TEST': outcomes}, advertencias=[],
            cortes={kind: dict(criterio='FECHAS', desde=kwargs['fecha_inicial'].isoformat(), hasta=kwargs['fecha_final'].isoformat()) for kind in ('ingreso', 'egreso')})

    def calculate(self):
        return api.calcular_preconciliacion(self.final.id,
            PreconciliacionCalculoEntrada(inventarios_iniciales=[self.middle.id, self.initial.id]), self.db)

    def test_consecutive_periods_are_chronological_and_do_not_duplicate_movements(self):
        result = self.calculate()
        periods = result['periodos_consecutivos']
        self.assertEqual([(p['inicial']['codigo'], p['final']['codigo']) for p in periods], [('INIT', 'MIDDLE'), ('MIDDLE', 'FINAL')])
        row = periods[0]['filas'][0]
        self.assertEqual((row['fisico_inicial'], row['ingresos'], row['egresos'], row['fisico_actual']), (10, 5, 1, 14))
        self.assertEqual(row['diferencia_conciliacion'], 0)
        self.assertEqual([d['remito'] for d in row['detalle_ingresos']], ['IN1'])
        self.assertEqual([d['remito'] for d in row['detalle_egresos']], ['OUT1'])
        self.assertEqual(periods[1]['filas'][0]['diferencia_conciliacion'], 0)
        self.assertIn('calculado_en', result)

    def test_manual_quantities_corrections_and_scrap_are_shared_with_the_same_audit(self):
        movement = audit.add_manual(self.final.id, dict(tipo='IN', codigo='TEST', cantidad=3, remito='MAN1', fecha='2026-11-02', observacion=''))
        audit.edit(self.final.id, movement['clave'], dict(cantidad_editada=4, verificado=True))
        audit.set_scrap(self.final.id, self.initial.id, 'TEST', 3)
        audit.set_scrap(self.final.id, self.middle.id, 'TEST', 1)
        result = self.calculate()
        row = result['periodos_consecutivos'][0]['filas'][0]
        self.assertEqual(row['ingresos'], 9)
        self.assertEqual(row['scrap'], 2)
        self.assertEqual(row['esperado'], 16)
        manual = next(d for d in row['detalle_ingresos'] if d['remito'] == 'MAN1')
        self.assertTrue(manual['verificado'])
        self.assertEqual(manual['cantidad'], 4)
        with audit.connection() as db:
            self.assertEqual(len(audit.read(db, self.final.id)['movimientos']), 5)
            self.assertEqual(audit.read(db, self.middle.id)['movimientos'], {})

    def test_historical_period_remains_evaluable_when_current_count_is_pending(self):
        self.final.items[0].conteo_fisico = None
        self.db.commit()
        result = self.calculate()
        self.assertTrue(result['periodos_consecutivos'][0]['filas'][0]['comparable'])
        self.assertFalse(result['periodos_consecutivos'][1]['filas'][0]['comparable'])
        self.assertIsNone(result['periodos_consecutivos'][1]['filas'][0]['diferencia_conciliacion'])

    def test_missing_component_is_not_a_counted_zero_and_does_not_inflate_quality(self):
        self.initial.items.append(InventarioItem(codigo='ONLY-INITIAL', descripcion='Anterior', etapa='TERMINADO', conteo_fisico=5))
        self.db.commit()
        result = self.calculate()
        row = next(r for p in result['escenarios'] for r in p['filas'] if r['codigo'] == 'ONLY-INITIAL')
        self.assertEqual(row['cobertura_final'], 'NO_INCLUIDO')
        self.assertIsNone(row['fisico_actual'])
        self.assertIsNone(row['conciliacion_ok'])
        self.assertEqual(result['indicadores']['conciliacion_integral']['total'], 1)
        self.assertEqual(result['indicadores']['total_piezas'], 2)

    def test_independent_system_control_can_be_available_without_initial_coverage(self):
        self.final.items.append(InventarioItem(codigo='NEW', descripcion='Nueva', etapa='TERMINADO', conteo_fisico=3, stock_sistema=3))
        self.db.commit()
        result = self.calculate()
        row = next(r for r in result['escenarios'][0]['filas'] if r['codigo'] == 'NEW')
        self.assertFalse(row['comparable'])
        self.assertTrue(row['comparacion_sistema_disponible'])
        self.assertTrue(row['sistema_ok'])
        self.assertIsNone(row['esperado'])
        self.assertEqual(result['indicadores']['sistema']['total'], 2)

    def test_non_nested_exclusions_or_cuts_are_not_presented_as_a_real_difference(self):
        result = self.calculate()
        older = next(s for s in result['escenarios'] if s['inicial']['id'] == self.initial.id)
        older['filas'][0]['detalle_ingresos'] = []
        periods = construir_periodos_consecutivos(result['escenarios'], result['inventario_final'], 5, api.dentro_tolerancia_comparacion)
        row = periods[0]['filas'][0]
        self.assertFalse(row['comparable'])
        self.assertIsNone(row['diferencia_conciliacion'])
        self.assertIn('no anidados', row['motivo_no_comparable'])
        result = self.calculate()
        result['escenarios'][0]['cortes']['ingreso']['hasta'] = '2026-11-06'
        periods = construir_periodos_consecutivos(result['escenarios'], result['inventario_final'], 5, api.dentro_tolerancia_comparacion)
        self.assertFalse(periods[0]['filas'][0]['comparable'])

    def test_same_date_or_failed_period_stays_explicitly_unavailable(self):
        result = self.calculate()
        scenarios = deepcopy(result['escenarios'])
        scenarios[0]['inicial']['fecha'] = scenarios[1]['inicial']['fecha']
        periods = construir_periodos_consecutivos(scenarios, result['inventario_final'], 5, api.dentro_tolerancia_comparacion)
        self.assertIn('error', periods[0])
        self.assertEqual(periods[0]['filas'], [])

    def test_saved_calculation_and_excel_preserve_both_period_views(self):
        saved = api.guardar_analisis_preconciliacion(self.final.id,
            PreconciliacionGuardarEntrada(inventarios_iniciales=[self.middle.id, self.initial.id], nombre='Comparación'), self.db)
        record = audit.get_analysis(saved['id'])
        self.assertEqual(record['calculo']['periodos_consecutivos'], saved['calculo']['periodos_consecutivos'])
        self.assertIn('actualizado_en', saved)
        self.assertIsNotNone(datetime.fromisoformat(saved['actualizado_en']).tzinfo)
        book = load_workbook(crear_excel_preconciliacion(self.final, saved['calculo'], {}, [], 'COMPARACION'))
        self.assertEqual(book.sheetnames[:4], ['Acumulados', 'Consecutivos', 'Sistema actual', 'Cortes y advertencias'])
        self.assertEqual(book['Consecutivos']['G2'].value, 10)
        self.assertEqual(book['Consecutivos']['H2'].value, 5)
        self.assertEqual(book['Consecutivos']['M2'].value, 0)
        self.assertEqual(len(audit.list_analyses()), 1)
