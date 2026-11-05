"""Análisis provisorios y actualización de su fotografía sin perder auditorías."""
import os
os.environ.setdefault('DATABASE_URL','mysql+pymysql://test:test@127.0.0.1/test')
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database import Base
from app.models import Inventario,InventarioItem
from app import preconciliation_audit as audit
from app.routers import api
from app.schemas import PreconciliacionGuardarEntrada,PreconciliacionCalculoEntrada
from app.services.piece_provider import _recorrer_estructura


class OpenStockAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine)
        self.temp=TemporaryDirectory()
        self.patches=[patch('app.services.movements.obtener_estructura_recursiva',side_effect=lambda code:_recorrer_estructura(code,lambda _:[],20)),
            patch.object(api,'obtener_estructura_recursiva',side_effect=lambda code:_recorrer_estructura(code,lambda _:[],20)),
            patch.object(audit,'STORE_PATH',Path(self.temp.name)/'audit.db'),
            patch.object(api,'notas_inventario',return_value={'TEST':{'observacion':'Nota a conservar','estado':'PENDIENTE'}}),
            patch.object(api,'buscar_pieza',return_value=None),
            patch.object(api,'buscar_material',return_value=None),
            patch.object(api,'buscar_codigos_cliente_piezas',return_value={}),
            patch.object(api,'obtener_ajustes_sistema',return_value={}),
            patch.object(api,'calcular_movimientos',return_value={'ingresos_por_codigo':{},'egresos_por_codigo':{},'detalles_ingreso':{},'detalles_egreso':{},'advertencias':[],'criterios':{}})]
        for item in self.patches:item.start()
        self.initial=Inventario(codigo='INIT',cliente='Cliente',fecha=date(2026,11,1),responsable='Test',estado='Cerrado',
            items=[InventarioItem(codigo='TEST',descripcion='Pieza',etapa='TERMINADO',stock_sistema=10,conteo_fisico=10)])
        self.final=Inventario(codigo='FINAL',cliente='Cliente',fecha=date(2026,11,5),responsable='Test',estado='En conteo',
            items=[InventarioItem(codigo='TEST',descripcion='Pieza',etapa='TERMINADO',stock_sistema=10,conteo_fisico=None)])
        self.db.add_all([self.initial,self.final]);self.db.commit()

    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.db.close();self.engine.dispose();self.temp.cleanup()

    def test_selector_includes_open_inventory_without_complete_codes(self):
        available=api.inventarios_disponibles_preconciliacion(self.db)
        row=next(item for item in available if item['id']==self.final.id)
        self.assertEqual(row['estado'],'En conteo')
        self.assertEqual(row['contados'],0)

    def test_incomplete_final_stays_provisional_without_inventing_zero_counts(self):
        result=api.calcular_preconciliacion(self.final.id,PreconciliacionCalculoEntrada(inventarios_iniciales=[self.initial.id]),self.db)
        self.assertEqual(result['inventario_final']['estado'],'En conteo')
        self.assertEqual(result['inventario_final']['contados'],0)
        rows=result['escenarios'][0]['filas']
        self.assertEqual([row['codigo'] for row in rows],['TEST'])
        self.assertEqual(rows[0]['esperado'],10)
        self.assertIsNone(rows[0]['fisico_actual'])
        self.assertIsNone(rows[0]['diferencia_conciliacion'])
        self.assertFalse(rows[0]['conteo_completo'])
        self.assertEqual(result['indicadores']['piezas_pendientes'],1)
        self.assertIsNone(result['indicadores']['conciliacion_integral']['porcentaje'])

    def test_refresh_updates_same_analysis_after_closing_and_keeps_notes_and_audit(self):
        saved=api.guardar_analisis_preconciliacion(self.final.id,PreconciliacionGuardarEntrada(inventarios_iniciales=[self.initial.id],nombre='Preparación'),self.db)
        original=audit.get_analysis(saved['id'])
        with audit.connection() as db:
            audit.write(db,self.final.id,{'movimientos':{},'scrap':{},'test_marker':'auditoria preservada'})
        self.final.items[0].conteo_fisico=9
        self.final.estado='Cerrado';self.db.commit()
        refreshed=api.actualizar_final_analisis(saved['id'],self.db)
        record=refreshed['analisis']
        self.assertEqual(record['id'],saved['id'])
        self.assertEqual(record['nombre'],'Preparación')
        self.assertEqual(record['creado_en'],original['creado_en'])
        self.assertEqual(record['inventarios_iniciales'],[self.initial.id])
        self.assertEqual(record['calculo']['inventario_final']['estado'],'Cerrado')
        self.assertEqual(refreshed['setup']['final']['contados'],1)
        rows=record['calculo']['escenarios'][0]['filas']
        self.assertTrue(rows,record['calculo']['escenarios'])
        self.assertEqual(rows[0]['conteo_actual'],9)
        self.assertEqual(record['calculo']['notas_guardadas']['TEST']['observacion'],'Nota a conservar')
        with audit.connection() as db:
            self.assertEqual(audit.read(db,self.final.id)['test_marker'],'auditoria preservada')
        self.assertEqual(len(audit.list_analyses()),1)
        again=api.actualizar_final_analisis(saved['id'],self.db)
        self.assertEqual(again['analisis']['id'],saved['id'])
        self.assertEqual(len(audit.list_analyses()),1)

    def test_missing_analysis_is_not_recreated(self):
        with self.assertRaises(HTTPException) as caught:
            api.actualizar_final_analisis('missing',self.db)
        self.assertEqual(caught.exception.status_code,404)
        self.assertFalse(audit.update_analysis_calculation('missing',{}))
        self.assertEqual(audit.list_analyses(),[])

    def test_failed_refresh_keeps_previous_saved_calculation(self):
        saved=api.guardar_analisis_preconciliacion(self.final.id,PreconciliacionGuardarEntrada(inventarios_iniciales=[self.initial.id],nombre='Conservar'),self.db)
        before=audit.get_analysis(saved['id'])
        with patch.object(api,'calcular_preconciliacion',side_effect=HTTPException(status_code=422,detail='No comparable')):
            with self.assertRaises(HTTPException):api.actualizar_final_analisis(saved['id'],self.db)
        self.assertEqual(audit.get_analysis(saved['id']),before)

    def test_union_includes_initial_only_final_only_and_partial_codes(self):
        self.initial.items.append(InventarioItem(codigo='SOLO-INICIAL',descripcion='Anterior',etapa='TERMINADO',conteo_fisico=3))
        self.final.items.extend([
            InventarioItem(codigo='SOLO-FINAL',descripcion='Nueva',etapa='TERMINADO',conteo_fisico=7),
            InventarioItem(codigo='TEST',descripcion='Otra ubicación',etapa='TERMINADO',conteo_fisico=4),
        ])
        self.db.commit()
        result=api.calcular_preconciliacion(self.final.id,PreconciliacionCalculoEntrada(inventarios_iniciales=[self.initial.id]),self.db)
        rows={row['codigo']:row for row in result['escenarios'][0]['filas']}
        self.assertEqual(set(rows),{'TEST','SOLO-INICIAL','SOLO-FINAL'})
        self.assertEqual(rows['TEST']['conteo_parcial'],4)
        self.assertIsNone(rows['TEST']['diferencia_conciliacion'])
        self.assertEqual(rows['SOLO-INICIAL']['fisico_inicial'],3)
        self.assertIsNone(rows['SOLO-INICIAL']['fisico_actual'])
        self.assertFalse(rows['SOLO-INICIAL']['comparable'])
        self.assertIsNone(rows['SOLO-FINAL']['fisico_inicial'])
        self.assertFalse(rows['SOLO-FINAL']['comparable'])
        self.assertEqual(rows['SOLO-FINAL']['fisico_actual'],7)

    def test_recursive_explosion_and_real_movements_are_limited_to_inventory_universe(self):
        from app.services import movements
        tree={'PADRE':[('SUB',2)], 'SUB':[('COMP',3)]}
        structure=lambda code:_recorrer_estructura(code,lambda c:tree.get(c,[]),20)
        self.initial.items=[InventarioItem(codigo='PADRE',descripcion='Conjunto',etapa='TERMINADO',conteo_fisico=10)]
        self.final.items=[InventarioItem(codigo='COMP',descripcion='Componente',etapa='TERMINADO',conteo_fisico=None)]
        self.db.commit()
        income={'codigo':'MP-COMP','cantidad':12,'remito':'101','remito_numero':101,'fecha':'2026-11-03'}
        outcomes=[{'codigo_pieza':c,'cantidad':q,'remito':r,'remito_numero':int(r),'fecha':'2026-11-03'}
                  for c,q,r in [('PADRE',2,'102'),('SUB',1,'103'),('COMP',4,'104')]]
        def income_rows(a,b,mapping):
            self.assertEqual(mapping,{'MP-COMP':{'COMP'}})
            return [income]
        def outcome_rows(a,b,codes):
            self.assertEqual(codes,{'PADRE','SUB','COMP'})
            self.assertNotIn('AJENA',codes)
            return outcomes
        with patch.object(api,'obtener_estructura_recursiva',side_effect=structure), \
             patch.object(movements,'obtener_estructura_recursiva',side_effect=structure), \
             patch.object(api,'calcular_movimientos',side_effect=movements.calcular_movimientos), \
             patch.object(movements,'_materiales_por_pieza',return_value={'MP-COMP':{'COMP'}}), \
             patch.object(movements,'_fechas_cortes_ingreso',return_value={}), \
             patch.object(movements,'_fechas_cortes_egreso',return_value={}), \
             patch.object(movements,'_filas_ingresos_con_limites',side_effect=income_rows), \
             patch.object(movements,'_filas_egresos_con_limites',side_effect=outcome_rows):
            result=api.calcular_preconciliacion(self.final.id,PreconciliacionCalculoEntrada(inventarios_iniciales=[self.initial.id]),self.db)
            rows=result['escenarios'][0]['filas']
            self.assertEqual([row['codigo'] for row in rows],['COMP'])
            row=rows[0]
            self.assertEqual(row['fisico_inicial'],60)
            self.assertEqual(row['ingresos'],12)
            self.assertEqual(row['egresos'],19)  # PADRE x6, SUB x3, COMP x1
            self.assertEqual(row['esperado'],53)
            self.assertIsNone(row['diferencia_conciliacion'])
            self.final.items[0].conteo_fisico=53;self.db.commit()
            refreshed=api.calcular_preconciliacion(self.final.id,PreconciliacionCalculoEntrada(inventarios_iniciales=[self.initial.id]),self.db)
            self.assertEqual(refreshed['escenarios'][0]['filas'][0]['diferencia_conciliacion'],0)
            self.assertTrue(refreshed['escenarios'][0]['filas'][0]['conciliacion_ok'])

    def test_provisional_excel_does_not_turn_missing_count_into_zero_difference(self):
        from app.services.preconciliation_excel import crear_excel_preconciliacion
        from openpyxl import load_workbook
        result=api.calcular_preconciliacion(self.final.id,PreconciliacionCalculoEntrada(inventarios_iniciales=[self.initial.id]),self.db)
        book=load_workbook(crear_excel_preconciliacion(self.final,result,{},[],"CONCILIACION"))
        sheet=book['Conciliación']
        self.assertEqual(sheet['A5'].value,'TEST')
        self.assertEqual(sheet['I5'].value,'Conteo pendiente')
        self.assertIsNone(sheet['J5'].value)
        self.assertEqual(sheet['H5'].value,'=D5+E5-F5-G5')
        book=load_workbook(crear_excel_preconciliacion(self.final,result,{},[],"ANALISIS"))
        sheet=book['Análisis general']
        self.assertEqual(sheet['D5'].value,'Conteo pendiente')
        self.assertIsNone(sheet['R5'].value)
        self.assertIsNone(sheet['U5'].value)

    def test_shared_material_union_does_not_duplicate_lot_or_income(self):
        self.initial.items=[
            InventarioItem(codigo='P1',codigo_material='MP',descripcion='P1',lote='L1',etapa='MATERIAL',conteo_fisico=10),
            InventarioItem(codigo='P2',codigo_material='MP',descripcion='P2',lote='L1',etapa='MATERIAL',conteo_fisico=10),
        ]
        self.final.items=[InventarioItem(codigo='P1',codigo_material='MP',descripcion='P1',lote='L1',etapa='MATERIAL',conteo_fisico=None)]
        self.db.commit()
        income={'remito':'100','fecha':'2026-11-03','codigo_material':'MP','cantidad':5}
        movements={'ingresos_por_codigo':{'P1':5,'P2':5},'egresos_por_codigo':{},
                    'detalles_ingreso':{c:[dict(income,codigo=c)] for c in ('P1','P2')},'detalles_egreso':{},'advertencias':[]}
        with patch.object(api,'calcular_movimientos',return_value=movements):
            result=api.calcular_preconciliacion(self.final.id,PreconciliacionCalculoEntrada(inventarios_iniciales=[self.initial.id]),self.db)
        rows=result['escenarios'][0]['filas']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['codigo'],'MP:MP')
        self.assertEqual(rows[0]['fisico_inicial'],10)
        self.assertEqual(rows[0]['ingresos'],5)
        self.assertEqual(rows[0]['esperado'],15)
        self.assertFalse(rows[0]['conteo_completo'])
