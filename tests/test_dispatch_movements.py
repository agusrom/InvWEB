"""Despachos reales del período, usando SQL de lectura sobre tablas temporales."""
import os
os.environ.setdefault('DATABASE_URL', 'mysql+pymysql://test:test@127.0.0.1/test')
from datetime import date, datetime
from unittest.mock import patch
import unittest
from sqlalchemy import create_engine, event, text
from app.services import movements as service
from app.services.piece_provider import _recorrer_estructura


class DispatchMovementsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        @event.listens_for(self.engine, 'connect')
        def sql_functions(connection, _record):
            connection.create_function('SUBSTRING_INDEX', 3, lambda value, sep, n: sep.join(str(value).split(sep)[n:]) if n < 0 else sep.join(str(value).split(sep)[:n]))
        with self.engine.begin() as db:
            db.exec_driver_sql('CREATE TABLE produc10 (VCOD_ TEXT, GCOD_ TEXT, QXUN_ REAL)')
            db.exec_driver_sql('CREATE TABLE produc08 (CDOC_ TEXT, FECH_ TEXT, GCOD_ TEXT, CANT_ REAL, STAT_ TEXT, LACTIVO_ INTEGER)')
            db.exec_driver_sql('CREATE TABLE mtprim06 (RMTO_ TEXT, FECH_ TEXT, CMAT_ TEXT, CANT_ REAL, CODI_ TEXT)')
            db.exec_driver_sql("INSERT INTO produc10 VALUES ('PT', 'SUB', 2), ('SUB', 'COMP', 3), ('PT','AJENO', 9)")
        self.tree = {'PT': [('SUB', 2), ('AJENO', 9)], 'SUB': [('COMP', 3)]}
        self.patches = [patch.object(service, 'production_engine', self.engine),
            patch.object(service, '_materiales_por_pieza', return_value={}),
            patch.object(service, '_fechas_cortes_ingreso', return_value={}),
            patch.object(service, '_fechas_cortes_egreso', return_value={}),
            patch.object(service, 'obtener_estructura_recursiva', side_effect=lambda code: _recorrer_estructura(code, lambda c: self.tree.get(c, []), 20))]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.engine.dispose()

    def dispatch(self, code, quantity, when, remito='E-100', status='D', active=1):
        with self.engine.begin() as db:
            db.execute(text('INSERT INTO produc08 VALUES (:r,:f,:c,:q,:s,:a)'), dict(r=remito, f=when, c=code, q=quantity, s=status, a=active))

    def calculate(self, parents=None, results=None):
        return service.calcular_movimientos('', '', '', '', date(2026, 11, 1), date(2026, 11, 5),
            codigos_padre=parents or {'COMP'}, codigos_resultado=results or {'COMP'})

    def test_finished_product_absent_from_inventory_is_found_and_exploded(self):
        self.dispatch('PT', 2, '2026-11-03 12:00:00')
        result = self.calculate()
        self.assertEqual(result['egresos_por_codigo'], {'COMP': 12})
        self.assertEqual(result['detalles_egreso']['COMP'][0]['pieza_origen'], 'PT')
        self.assertEqual(result['detalles_egreso']['COMP'][0]['uso'], 6)
        self.assertNotIn('AJENO', result['egresos_por_codigo'])

    def test_direct_dispatches_and_subassemblies_accumulate_once(self):
        self.dispatch('PT', 2, '2026-11-03 12:00:00', 'E-100')
        self.dispatch('SUB', 3, '2026-11-03 13:00:00', 'E-101')
        self.dispatch('COMP', 4, '2026-11-04 12:00:00', 'E-102')
        self.dispatch('OTRA', 999, '2026-11-03 12:00:00', 'E-103')
        result = self.calculate()
        self.assertEqual(result['egresos_por_codigo'], {'COMP': 25})
        self.assertEqual(len(result['detalles_egreso']['COMP']), 3)

    def test_direct_finished_piece_is_not_lost_regardless_of_inventory_state(self):
        # El servicio recibe códigos/fechas; nunca filtra por estado abierto/cerrado.
        self.tree = {}
        self.dispatch('PIEZA', 7, '2026-11-05 18:20:00')
        result = self.calculate({'PIEZA'}, {'PIEZA'})
        self.assertEqual(result['egresos_por_codigo'], {'PIEZA': 7})

    def test_date_cuts_exclude_initial_day_and_include_entire_final_day(self):
        for index, when in enumerate(('2026-11-01 15:00:00', '2026-11-02 00:00:00', '2026-11-05 23:59:59', '2026-11-06 00:00:00')):
            self.dispatch('COMP', 1, when, f'E-{100+index}')
        rows = service._filas_egresos_con_limites(date(2026, 11, 1), date(2026, 11, 5), {'COMP'})
        self.assertEqual([r['remito'] for r in rows], ['E-101', 'E-102'])

    def test_remittance_timestamp_cuts_remain_exact(self):
        for index, when in enumerate(('2026-11-01 10:00:00', '2026-11-01 10:00:01', '2026-11-05 18:00:00', '2026-11-05 18:00:01')):
            self.dispatch('COMP', 1, when, f'E-{100+index}')
        rows = service._filas_egresos_con_limites(datetime(2026, 11, 1, 10), datetime(2026, 11, 5, 18), {'COMP'})
        self.assertEqual([r['remito'] for r in rows], ['E-101', 'E-102'])

    def test_status_and_code_normalization_keep_valid_dispatches(self):
        self.dispatch(' comp ', 4, '2026-11-03 12:00:00', status=' d ', active=0)
        self.dispatch('COMP', 8, '2026-11-03 12:00:00', 'E-101', status='P')
        result = self.calculate()
        self.assertEqual(result['egresos_por_codigo'], {'COMP': 4})

    def test_income_uses_same_date_boundary_policy(self):
        with self.engine.begin() as db:
            for index, when in enumerate(('2026-11-01 15:00:00','2026-11-05 23:59:59','2026-11-06 00:00:00')):
                db.execute(text('INSERT INTO mtprim06 VALUES (:r,:f,:c,1,:s)'), dict(r=str(index+1), f=when, c='MP', s='RC'))
        rows = service._filas_ingresos_con_limites(date(2026,11,1),date(2026,11,5),{'MP':{'COMP'}})
        self.assertEqual([r['remito'] for r in rows], ['2'])

    def test_inverse_structure_handles_cycles_and_refuses_truncation(self):
        with self.engine.begin() as db:
            db.exec_driver_sql("INSERT INTO produc10 VALUES ('COMP', 'PT', 1)")
        self.assertEqual(service._padres_de_componentes({'COMP'}), {'SUB','PT'})
        with self.assertRaises(RuntimeError): service._padres_de_componentes({'COMP'}, max_niveles=1)

    def test_api_and_audit_keep_automatic_dispatches_for_open_and_closed_inventories(self):
        from tests import test_open_stock_analysis as fixtures
        from app.routers import api
        from app.schemas import PreconciliacionCalculoEntrada
        fixture = fixtures.OpenStockAnalysisTests()
        fixture.setUp()
        try:
            self.dispatch('TEST', 3, '2026-11-05 18:20:00')
            with patch.object(api, 'calcular_movimientos', side_effect=service.calcular_movimientos):
                for state in ('En conteo', 'Cerrado'):
                    fixture.final.estado = state
                    fixture.final.items[0].conteo_fisico = None if state == 'En conteo' else 7
                    fixture.db.commit()
                    result = api.calcular_preconciliacion(fixture.final.id, PreconciliacionCalculoEntrada(inventarios_iniciales=[fixture.initial.id]), fixture.db)
                    row = result['escenarios'][0]['filas'][0]
                    self.assertEqual(row['egresos'], 3)
                    self.assertEqual(row['detalle_egresos'][0]['pieza_origen'], 'TEST')
                    self.assertTrue(any(m['tipo'] == 'OUT' and m['codigo'] == 'TEST' for m in result['movimientos']))
                    self.assertEqual(result['version_movimientos'], 2)
                    self.assertEqual(result['escenarios'][0]['diagnostico_egresos']['despachos_aplicados'], 1)
        finally:
            fixture.tearDown()

    def test_missing_source_is_reported_explicitly(self):
        with patch.object(service, 'production_engine', None):
            result = self.calculate({'SIN-ESTRUCTURA'}, {'SIN-ESTRUCTURA'})
        self.assertFalse(result['diagnostico_egresos']['fuente_configurada'])
        self.assertTrue(any('No hay conexión productiva' in warning for warning in result['advertencias']))
