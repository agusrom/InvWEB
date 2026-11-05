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
        self.assertEqual(result['escenarios'][0]['filas'],[])
        self.assertIn('error',result['escenarios'][0])

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
