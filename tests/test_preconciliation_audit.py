"""Pruebas aisladas: no requieren conexión a MySQL ni alteran datos reales."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import unittest
from types import SimpleNamespace
from app import preconciliation_audit as audit


def scenarios():
    rows = []
    for code, use in [('P1', 2), ('P2', 3)]:
        rows.append(dict(codigo=code, descripcion='Pieza de prueba ' + code, fisico_inicial=100,
            conteo_actual=120, conteo_explotado_actual=110, fisico_actual=110,
            sistema_actual=120, diferencia_sistema=0, sistema_ok=True,
            detalle_sistema=dict(materia_prima=500,en_proceso=70,producto_terminado=50,stock_asignado=5,total_productivo=120),
            detalle_ingresos=[dict(remito='001245', fecha='2026-07-14', codigo_material='MAT1', codigo=code, cantidad=50)],
            detalle_egresos=[dict(remito='E-001', fecha='2026-07-15', pieza_origen='PADRE', cantidad_pieza=10, uso=use, cantidad_equivalente=10*use)]))
    return [dict(inicial=dict(id=1, codigo='INV-JUN', fecha='2026-06-30'), filas=deepcopy(rows), advertencias=[]),
            dict(inicial=dict(id=2, codigo='INV-JUL', fecha='2026-07-01'), filas=deepcopy(rows), advertencias=['Corte de ejemplo: verificar remito inicial.']),
            dict(inicial=dict(id=3, codigo='INV-AGO', fecha='2026-08-01'), filas=[dict(r, detalle_ingresos=[], detalle_egresos=[]) for r in deepcopy(rows)], advertencias=[])]


def calculate(data=None, final_id=99):
    return audit.reconcile(final_id, '2026-08-31', data if data is not None else scenarios(), 0,
        lambda a,b,t: abs(a-b) < 0.00001,
        lambda m,codes: {code: 1 for code in codes if m['codigo'] == code})


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.old = audit.STORE_PATH
        self.path = Path(__file__).resolve().parent / (uuid4().hex + '.sqlite3')
        audit.STORE_PATH = self.path
    def tearDown(self):
        audit.STORE_PATH = self.old
        self.path.unlink(missing_ok=True)
    def test_unique_source_across_scenarios_and_components(self):
        result = calculate()
        self.assertEqual(len(result['movimientos']), 2)
        self.assertEqual(result['movimientos'][0]['escenarios'], [1,2])
    def test_correction_propagates_and_recalculation_persists(self):
        result = calculate()
        key = next(m['clave'] for m in result['movimientos'] if m['tipo'] == 'OUT')
        audit.edit(99,key,dict(cantidad_editada=4,verificado=True,observacion='Comprobado'))
        for _ in range(2):
            result = calculate()
            for scenario in result['escenarios'][:2]:
                self.assertEqual([r['egresos'] for r in scenario['filas']], [8,12])
                self.assertTrue(scenario['filas'][0]['detalle_egresos'][0]['verificado'])
                self.assertEqual(scenario['filas'][0]['conteo_actual'], 120)
                self.assertEqual(scenario['filas'][0]['conteo_explotado_actual'], 110)
    def test_zero_and_restore_original(self):
        key = calculate()['movimientos'][0]['clave']
        audit.edit(99,key,dict(cantidad_editada=0))
        self.assertEqual(calculate()['escenarios'][0]['filas'][0]['ingresos'],0)
        audit.edit(99,key,dict(cantidad_editada=None))
        self.assertEqual(calculate()['escenarios'][0]['filas'][0]['ingresos'],50)

    def test_whole_remittance_is_saved_atomically_and_recalculates_only_if_needed(self):
        first = audit.add_manual(99, dict(
            tipo='IN', fecha='2026-07-14', remito='R-LOTE', codigo='P1', cantidad=5,
        ))['clave']
        second = audit.add_manual(99, dict(
            tipo='IN', fecha='2026-07-14', remito='R-LOTE', codigo='P2', cantidad=7,
        ))['clave']
        controls = [
            dict(clave=first, cantidad_editada=None, verificado=True,
                 observacion='Revisado', excluidos=[]),
            dict(clave=second, cantidad_editada=None, verificado=True,
                 observacion='Revisado', excluidos=[]),
        ]
        saved = audit.edit_many(99, controls)
        self.assertFalse(saved['requiere_recalculo'])
        self.assertTrue(all(item['verificado'] for item in saved['movimientos']))
        controls[1]['cantidad_editada'] = 9
        saved = audit.edit_many(99, controls)
        self.assertTrue(saved['requiere_recalculo'])
        self.assertEqual(saved['movimientos'][1]['cantidad'], 9)

    def test_batch_rejects_mixed_remittances_without_partial_changes(self):
        first = audit.add_manual(99, dict(
            tipo='IN', fecha='2026-07-14', remito='R-1', codigo='P1', cantidad=5,
        ))['clave']
        second = audit.add_manual(99, dict(
            tipo='IN', fecha='2026-07-14', remito='R-2', codigo='P2', cantidad=7,
        ))['clave']
        with self.assertRaises(ValueError):
            audit.edit_many(99, [
                dict(clave=first, cantidad_editada=None, verificado=True,
                     observacion='', excluidos=[]),
                dict(clave=second, cantidad_editada=None, verificado=True,
                     observacion='', excluidos=[]),
            ])
        with audit.connection() as db:
            data = audit.read(db, 99)
        self.assertFalse(data['movimientos'][first]['verificado'])
        self.assertFalse(data['movimientos'][second]['verificado'])
    def test_exclusion_only_one_scenario(self):
        key = calculate()['movimientos'][0]['clave']
        audit.edit(99,key,dict(excluidos=[2]))
        result = calculate()
        self.assertEqual(result['escenarios'][0]['filas'][0]['ingresos'],50)
        self.assertEqual(result['escenarios'][1]['filas'][0]['ingresos'],0)
    def test_manual_boundaries_exclusion_and_delete(self):
        keys = []
        for day in ['2026-06-30','2026-07-01','2026-08-31']:
            keys.append(audit.add_manual(99,dict(tipo='IN',fecha=day,remito=day,codigo='P1',cantidad=5))['clave'])
        result = calculate()
        manuals = {m['clave']:m for m in result['movimientos'] if m['manual']}
        self.assertEqual(manuals[keys[0]]['escenarios'],[])
        self.assertEqual(manuals[keys[1]]['escenarios'],[1])
        self.assertEqual(manuals[keys[2]]['escenarios'],[1,2,3])
        audit.edit(99,keys[2],dict(excluidos=[2]))
        self.assertEqual(calculate()['escenarios'][1]['filas'][0]['ingresos'],50)
        audit.edit(99,keys[2],delete=True)
        self.assertEqual(calculate()['escenarios'][2]['filas'][0]['ingresos'],0)
    def test_automatic_cannot_delete(self):
        with self.assertRaises(ValueError):
            audit.edit(99,calculate()['movimientos'][0]['clave'],delete=True)
    def test_scrap_by_piece_and_period(self):
        audit.set_scrap(99,1,'P1',7)
        result=calculate()
        self.assertEqual(result['escenarios'][0]['filas'][0]['esperado'],123)
        self.assertEqual(result['escenarios'][1]['filas'][0]['esperado'],130)
        self.assertEqual(result['escenarios'][0]['filas'][1]['scrap'],0)
    def test_final_inventory_isolation(self):
        key = calculate()['movimientos'][0]['clave']
        audit.edit(99,key,dict(cantidad_editada=4))
        self.assertEqual(calculate(final_id=100)['movimientos'][0]['cantidad'],50)
    def test_unselected_scenario_does_not_erase_control(self):
        key = calculate()['movimientos'][0]['clave']
        audit.edit(99,key,dict(cantidad_editada=4, excluidos=[1]))
        calculate(scenarios()[2:])
        result = calculate()
        self.assertEqual(result['movimientos'][0]['cantidad'],4)
        self.assertEqual(result['escenarios'][0]['filas'][0]['ingresos'],0)
    def test_unmatched_manual_is_warned(self):
        audit.add_manual(99,dict(tipo='IN',fecha='2026-07-14',remito='X',codigo='UNKNOWN',cantidad=5))
        result=calculate()
        self.assertIn('sin pieza comparable', result['escenarios'][0]['advertencias'][0])
        self.assertEqual(result['escenarios'][0]['filas'][0]['ingresos'],50)

    def test_direct_count_and_exploded_count_are_independent(self):
        result = calculate()
        row = result['escenarios'][0]['filas'][0]
        # La auditoría recalcula esperado/conciliación únicamente con el
        # explotado; el conteo directo queda reservado para sistema.
        self.assertEqual(row['conteo_actual'], 120)
        self.assertEqual(row['conteo_explotado_actual'], 110)
        self.assertEqual(row['diferencia_conciliacion'], -20)
        self.assertEqual(row['diferencia_sistema'], 0)

    def test_system_adjustments_are_evidence_and_are_not_compared_with_expected_stock(self):
        data = scenarios()[:1]
        row = data[0]["filas"][0]
        row["ajustes_sistema"] = [{"cantidad": -10, "etapa": "TERMINADO"}]
        row["resumen_ajustes_sistema"] = {"cantidad": 1, "neto": -10}
        result = calculate(data)
        calculated = result["escenarios"][0]["filas"][0]
        self.assertEqual(calculated["esperado"], 130)
        self.assertEqual(calculated["resumen_ajustes_sistema"]["neto"], -10)
        self.assertNotIn("diferencia_sistema_esperado", calculated)
        self.assertNotIn("ajuste_explica_sistema", calculated)

    def test_analysis_snapshot_is_saved_and_reopened(self):
        result = calculate()
        analysis_id = audit.save_analysis(99, 'INV-FINAL', result['escenarios'], result, 'Cierre de agosto')
        saved = audit.get_analysis(analysis_id)
        self.assertEqual(saved['final_id'], 99)
        self.assertEqual(saved['inventarios_iniciales'], [1, 2, 3])
        self.assertEqual(saved['nombre'], 'Cierre de agosto')
        self.assertEqual(saved['calculo']['escenarios'][0]['filas'][0]['codigo'], 'P1')
        self.assertEqual(audit.list_analyses()[0]['id'], analysis_id)

    def test_saved_analysis_can_be_deleted_without_erasing_audit(self):
        result = calculate()
        movement_key = result['movimientos'][0]['clave']
        analysis_id = audit.save_analysis(99, 'INV-FINAL', result['escenarios'], result, 'Temporal')
        self.assertTrue(audit.delete_analysis(analysis_id))
        self.assertIsNone(audit.get_analysis(analysis_id))
        self.assertFalse(audit.delete_analysis(analysis_id))
        with audit.connection() as db:
            self.assertIn(movement_key, audit.read(db, 99)['movimientos'])

if __name__ == '__main__':
    unittest.main()
