"""Listado acotado, métricas equivalentes y consultas solo de lectura."""
import os
os.environ.setdefault("DATABASE_URL", "mysql+pymysql://test:test@127.0.0.1/test")
from datetime import date,timedelta
import unittest
from unittest.mock import patch
from sqlalchemy import Column,Date,Integer,MetaData,Table,create_engine,event,select
from sqlalchemy.orm import Session
from app.database import Base
from app.models import ConfiguracionSistema,Inventario,InventarioItem,Plantilla,ProgramacionInventario
from app.services.inventory_listing import inventarios_calendario,listar_inventarios,metricas_portada
from app.serializers import metricas_confiabilidad


class InventoryListingTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.cierres=Table('inventario_cierres',MetaData(),Column('inventario_id',Integer,primary_key=True),Column('mes_cierre',Date))
        self.cierres.create(self.engine)
        self.db=Session(self.engine)
        self.db.add(ConfiguracionSistema(clave='tolerancia_pct',valor='5',descripcion='test'))
        self.ids=[]
        for n in range(61):
            inv=Inventario(codigo=f'INV-PERF-{n:03}',cliente='Cliente A' if n%2 else 'Cliente B',
                fecha=date(2026,11,4)-timedelta(days=n),responsable='Operador',
                estado='Cerrado' if n%3==0 else 'En preparación',
                observaciones='literal 100%_dato' if n==1 else '',
                items=[InventarioItem(codigo='P1',descripcion='Pieza',etapa='TERMINADO',stock_sistema=100,conteo_fisico=104),
                       InventarioItem(codigo='P2',descripcion='Pieza',etapa='TERMINADO',stock_sistema=0,conteo_fisico=0),
                       InventarioItem(codigo='P3',descripcion='Pendiente',etapa='TERMINADO',stock_sistema=10,conteo_fisico=None)])
            self.db.add(inv);self.db.flush();self.ids.append(inv.id)
        self.db.commit()
        self.queries=[]
        event.listen(self.engine,'before_cursor_execute',self.capture)

    def capture(self,connection,cursor,statement,parameters,context,executemany):
        self.queries.append(statement)

    def tearDown(self):
        self.db.close();self.engine.dispose()

    def test_pages_are_bounded_stable_and_no_items_are_serialized(self):
        first=listar_inventarios(self.db,vista='TODOS')
        second=listar_inventarios(self.db,pagina=2,vista='TODOS')
        self.assertEqual(first['total'],61)
        self.assertEqual(first['paginas'],3)
        self.assertEqual(len(first['inventarios']),25)
        self.assertEqual(len(second['inventarios']),25)
        self.assertFalse({r['id'] for r in first['inventarios']} & {r['id'] for r in second['inventarios']})
        self.assertTrue(all('items' not in row for row in first['inventarios']))
        self.assertEqual(first['inventarios'][0]['id'],self.ids[0])
        self.assertEqual(listar_inventarios(self.db,pagina=99,vista='TODOS')['pagina'],3)

    def test_metrics_match_existing_rules_including_zero_pending_and_negative_stock(self):
        inv=self.db.get(Inventario,self.ids[1])
        inv.items.extend([
            InventarioItem(codigo='Z',descripcion='Cero diferente',stock_sistema=0,conteo_fisico=3),
            InventarioItem(codigo='N',descripcion='Negativo',stock_sistema=-100,conteo_fisico=-104),
            InventarioItem(codigo='S',descripcion='Sin sistema',stock_sistema=100,conteo_fisico=100,stock_pendiente=True),
            InventarioItem(codigo='E',descripcion='Límite',stock_sistema=100,conteo_fisico=105),
        ]);self.db.commit()
        old=metricas_confiabilidad(inv)
        row=listar_inventarios(self.db,buscar=inv.codigo,vista='TODOS')['inventarios'][0]
        for key,value in old.items():self.assertEqual(row[key],value,key)
        self.assertEqual(row['progreso'],round(6*100/7))
        self.assertEqual(row['resumen']['diferencias'],4)
        self.assertEqual(row['resumen']['fueraTolerancia'],1)
        self.assertEqual(row['resumen']['stockPendiente'],1)

    def test_search_filters_all_pages_and_escapes_literal_wildcards(self):
        self.assertEqual(listar_inventarios(self.db,buscar='100%_dato',vista='TODOS')['total'],1)
        self.assertEqual(listar_inventarios(self.db,buscar='100X_dato',vista='TODOS')['total'],0)
        self.assertEqual(listar_inventarios(self.db,buscar='cliente a',vista='TODOS')['total'],30)
        self.assertEqual(listar_inventarios(self.db,estado='Cerrado',vista='EN_CURSO')['total'],0)
        self.assertEqual(listar_inventarios(self.db,vista='REALIZADOS')['total'],21)

    def test_query_count_is_constant_and_reads_do_not_modify_schema_or_data(self):
        listar_inventarios(self.db,por_pagina=1,vista='TODOS')
        small=len(self.queries);self.queries.clear()
        listar_inventarios(self.db,por_pagina=50,vista='TODOS')
        self.assertEqual(len(self.queries),small)
        self.assertLessEqual(small,5)
        self.assertTrue(all(q.lstrip().upper().startswith('SELECT') for q in self.queries))

    def test_global_metrics_do_not_depend_on_page_or_filters(self):
        result=metricas_portada(self.db)
        self.assertEqual(result,dict(total=61,preparacion=40,conteo=0,diferencias=61))
        self.assertEqual(len(self.queries),1)

    def test_calendar_is_independent_of_listing_and_includes_scheduled_dates(self):
        inv=self.db.get(Inventario,self.ids[-1]);inv.fecha_programada=date(2026,11,5);self.db.commit()
        result=inventarios_calendario(self.db,date(2026,11,2),date(2026,11,8))
        self.assertIn(inv.id,{r['id'] for r in result})
        self.assertEqual(len(result),4)
        self.assertTrue(all('items' not in row for row in result))

    def test_closing_month_is_loaded_in_bulk_from_existing_table(self):
        self.db.execute(self.cierres.insert().values(inventario_id=self.ids[0],mes_cierre=date(2026,10,1)));self.db.commit()
        row=listar_inventarios(self.db,vista='TODOS')['inventarios'][0]
        self.assertEqual(row['mes_cierre'],'2026-10-01')

    def test_light_boot_does_not_serialize_all_inventory_details(self):
        from app.routers.api import obtener_inicio
        with patch('app.routers.api.listar_notas',return_value=[]),patch('app.routers.api.inventario_dict',side_effect=AssertionError('Carga completa no permitida')):
            result=obtener_inicio(ligero=True,db=self.db)
        self.assertEqual(result['inventarios'],[])


    def test_light_schedules_keep_latest_inventory_without_loading_its_items(self):
        from app.routers.api import obtener_inicio
        plantilla=Plantilla(nombre='Plantilla',cliente='Cliente A',items=[])
        schedule=ProgramacionInventario(plantilla=plantilla,fecha_proxima=date(2026,11,5),
            mes_cierre_proximo=date(2026,11,1),responsable='Operador',frecuencia='UNA_VEZ')
        self.db.add(schedule);self.db.flush()
        self.db.get(Inventario,self.ids[0]).programacion=schedule
        self.db.get(Inventario,self.ids[-1]).programacion=schedule
        self.db.commit();self.queries.clear()
        with patch('app.routers.api.listar_notas',return_value=[]),patch('app.routers.api.plantilla_dict',return_value={}),patch('app.routers.api.inventario_dict',side_effect=AssertionError('Carga completa no permitida')):
            data=obtener_inicio(ligero=True,db=self.db)
        self.assertEqual(data['programaciones'][0]['ejecuciones'],2)
        self.assertEqual(data['programaciones'][0]['ultimo_inventario']['id'],self.ids[-1])
        self.assertFalse(any('FROM inventario_items' in sql for sql in self.queries))

    def test_search_keeps_existing_scope_labels(self):
        inv=self.db.get(Inventario,self.ids[0]);inv.ambito='CLIENTE';self.db.commit()
        self.assertEqual(listar_inventarios(self.db,buscar='con cliente',vista='TODOS')['total'],1)

    def test_detail_includes_recount_headers_even_outside_the_current_page(self):
        from app.routers.home import detalle
        actual=self.db.get(Inventario,self.ids[0])
        with patch('app.routers.home.buscar_inventario',return_value=actual),patch('app.routers.home.inventario_dict',return_value={
            'id':actual.id,'relacion_reconteo':None,
            'reconteos_vinculados':[{'inventario_reconteo_id':self.ids[-1]}]}):
            data=detalle(actual.id,db=self.db)
        self.assertEqual(data['inventarios_relacionados'][0]['id'],self.ids[-1])
        self.assertNotIn('items',data['inventarios_relacionados'][0])
