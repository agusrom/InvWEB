"""Catálogos locales aislados y compatibilidad con datos históricos."""
import os
os.environ.setdefault('DATABASE_URL', 'mysql+pymysql://test:test@127.0.0.1/test')
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database import Base
from app.models import Inventario, Plantilla, TipoInventario, Sector, Persona
from app import catalog_database as store
from app.services import client_catalog as clients
from app.routers import api
from app.schemas import ClienteEntrada, PlantillaEntrada, UnificarClienteEntrada


class LocalCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.patch = patch.object(store, 'DATABASE_PATH', Path(self.temp.name) / 'catalogos.sqlite3')
        self.patch.start()
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all([
            Sector(id=7, nombre='Calidad', descripcion='Existente', orden=10),
            TipoInventario(codigo='PERSONALIZADO', nombre='Especial', motor='PIEZAS', modalidad='ESTANDAR', formato_impresion='FLUJO_HORIZONTAL'),
            Inventario(codigo='HIST-1', cliente='Acme SA', fecha=date(2026, 1, 1), responsable='María Pérez', estado='Cerrado'),
            Inventario(codigo='HIST-2', cliente=' ACME SA ', fecha=date(2026, 2, 1), responsable='María Pérez', estado='Cerrado'),
            Plantilla(nombre='Histórica', cliente='Acme S.A.', tipo_conteo='GLOBAL', tipo_inventario_codigo='PERSONALIZADO'),
        ])
        self.db.flush()
        self.db.add(Persona(id=9, nombre='María Pérez', sector_id=7, legajo='L9'))
        self.db.commit()
        self.sql = []
        event.listen(self.engine, 'before_cursor_execute', self.record)
        clients.importar_clientes(self.db)

    def record(self, conn, cursor, statement, params, context, executemany):
        self.sql.append(statement.strip().split()[0].upper())

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        store._engine(str(store.DATABASE_PATH.resolve())).dispose()
        self.patch.stop()
        self.temp.cleanup()
        clients._snapshot.cache_clear()

    def customer(self, name='Acme SA'):
        cid = clients.referencia(name)['cliente_id']
        return next(c for c in clients.listar(self.db) if c['id'] == cid)

    def test_bootstrap_only_reads_source_and_preserves_ids(self):
        self.assertTrue(self.sql)
        self.assertEqual(set(self.sql), {'SELECT'})
        self.assertEqual(self.db.get(Persona, 9).sector_id, 7)
        self.assertEqual(self.db.get(TipoInventario, 'PERSONALIZADO').nombre, 'Especial')
        self.assertEqual(len(clients.listar()), 2)  # Punctuation is not silently unified.
        self.assertEqual(clients.referencia('Acme SA')['cliente_id'], clients.referencia(' ACME SA ')['cliente_id'])

    def test_existing_catalogs_are_not_created_or_copied_to_sqlite(self):
        from sqlalchemy import inspect
        tables = set(inspect(store._engine(str(store.DATABASE_PATH.resolve()))).get_table_names())
        self.assertEqual(tables, {'clientes', 'cliente_nombres', 'catalogo_meta'})
        self.assertNotIn('personas', tables)
        self.assertNotIn('sectores', tables)
        self.assertNotIn('tipos_inventario', tables)
        catalogs = api.obtener_catalogos(self.db)
        self.assertEqual(catalogs['sectores'][0]['nombre'], 'Calidad')
        self.assertEqual(catalogs['personas'][0]['id'], 9)
        self.assertEqual(catalogs['tipos_inventario'][0]['codigo'], 'PERSONALIZADO')
        clients.importar_clientes(self.db)
        self.assertEqual(set(self.sql), {'SELECT'})

    def test_client_rename_retains_stable_value_and_old_names(self):
        old = self.customer()
        changed = api.modificar_cliente(old['id'], ClienteEntrada(nombre='Acme Argentina', aliases=['ACME Nacional']))
        self.assertEqual(changed['codigo'], old['codigo'])
        self.assertEqual(changed['valor'], old['valor'])
        self.assertEqual(clients.referencia('Acme SA')['cliente_nombre'], 'Acme Argentina')
        self.assertEqual(clients.referencia('ACME Nacional')['cliente_id'], old['id'])
        self.assertIn(' ACME SA ', clients.nombres_equivalentes('Acme Argentina'))
        clients.importar_clientes(self.db)
        self.assertEqual(clients.referencia('Acme SA')['cliente_nombre'], 'Acme Argentina')
        self.db.expire_all()
        self.assertEqual(self.db.scalar(select(Inventario).where(Inventario.codigo == 'HIST-1')).cliente, 'Acme SA')

    def test_invalid_duplicate_and_conflicting_aliases_are_atomic(self):
        before = clients.listar()
        with self.assertRaises(HTTPException):
            api.crear_cliente(ClienteEntrada(nombre='  ACME SA  '))
        with self.assertRaises(HTTPException):
            api.modificar_cliente(self.customer()['id'], ClienteEntrada(nombre='Nombre nuevo', aliases=['Acme S.A.']))
        with self.assertRaises(HTTPException):
            api.crear_cliente(ClienteEntrada(nombre='   '))
        self.assertEqual(clients.listar(), before)

    def test_unification_resolves_comparisons_and_preserves_history(self):
        first = self.customer()
        other = self.customer('Acme S.A.')
        api.unificar_cliente(other['id'], UnificarClienteEntrada(destino_id=first['id']))
        self.assertEqual(clients.referencia('Acme S.A.')['cliente_id'], first['id'])
        self.assertEqual(clients.valor_cliente('Acme S.A.'), first['valor'])
        self.assertIn('Acme S.A.', clients.nombres_equivalentes('Acme SA'))
        usage = clients.usos(self.db)[first['id']]
        self.assertEqual(usage, {'inventarios': 2, 'plantillas': 1})
        self.assertEqual(self.db.scalar(select(Plantilla)).cliente, 'Acme S.A.')
        with self.assertRaises(HTTPException):
            api.unificar_cliente(first['id'], UnificarClienteEntrada(destino_id=first['id']))
        with self.assertRaises(HTTPException):
            api.eliminar_cliente(first['id'], self.db)

    def test_inactive_clients_are_not_assigned_to_new_records(self):
        original = self.customer()
        api.modificar_cliente(original['id'], ClienteEntrada(nombre=original['nombre'], activo=False))
        with self.assertRaises(HTTPException):
            clients.valor_cliente(original['valor'])
        self.assertEqual(clients.valor_cliente(original['valor'], original['valor']), original['valor'])
        self.assertFalse(clients.referencia(original['valor'])['cliente_activo'])
        clients.importar_clientes(self.db)
        self.assertFalse(clients.referencia(original['valor'])['cliente_activo'])

    def test_delete_is_only_allowed_without_history(self):
        with self.assertRaises(HTTPException):
            api.eliminar_cliente(self.customer()['id'], self.db)
        unused = api.crear_cliente(ClienteEntrada(nombre='Sin uso'))
        api.eliminar_cliente(unused['id'], self.db)
        self.assertIsNone(clients.referencia('Sin uso')['cliente_id'])

    def test_new_sqlite_client_can_be_selected_with_existing_mysql_type(self):
        entry = PlantillaEntrada(nombre='Nueva plantilla', cliente='ACME SA', tipo_conteo='GLOBAL', tipo_inventario_codigo='PERSONALIZADO', items=[])
        with patch.object(api, 'validar_items_plantilla', return_value=[]), patch.object(api, 'guardar_tipos_items_plantilla'), patch.object(api, 'plantilla_dict', side_effect=lambda p: {'cliente': p.cliente, 'tipo': p.tipo_inventario_codigo}):
            result = api.crear_plantilla(entry, self.db)
        self.assertEqual(result['cliente'], self.customer()['valor'])
        self.assertEqual(result['tipo'], 'PERSONALIZADO')
        self.assertEqual(self.db.get(TipoInventario, 'PERSONALIZADO').nombre, 'Especial')

    def test_export_contains_portable_identities_and_aliases(self):
        response = api.exportar_clientes_locales()
        data = json.loads(response.body)
        self.assertEqual(data['version'], 1)
        self.assertIn('cliente_nombres', data['tablas'])
        self.assertNotIn('persona_nombres', data['tablas'])
        self.assertNotIn('sectores', data['tablas'])
        self.assertIn('clientes.json', response.headers['content-disposition'])

    def test_explicit_unification_makes_historical_inventories_comparable(self):
        from app.models import InventarioItem
        for inventory in self.db.scalars(select(Inventario)).all():
            inventory.items.append(InventarioItem(codigo='TEST', descripcion='Pieza', etapa='TERMINADO', conteo_fisico=1))
        final = Inventario(codigo='FINAL', cliente='Acme S.A.', fecha=date(2026, 3, 1), responsable='María Pérez', estado='En conteo')
        self.db.add(final); self.db.commit()
        with patch.object(api, 'notas_inventario', return_value={}):
            before = api.opciones_preconciliacion(final.id, self.db)
            self.assertEqual(before['iniciales'], [])
            api.unificar_cliente(self.customer('Acme S.A.')['id'], UnificarClienteEntrada(destino_id=self.customer()['id']))
            after = api.opciones_preconciliacion(final.id, self.db)
        self.assertEqual(len(after['iniciales']), 2)
        self.assertEqual(self.db.get(Inventario, final.id).cliente, 'Acme S.A.')
        from app.services.reports import construir_grafico_clientes
        graph = construir_grafico_clientes(self.db.scalars(select(Inventario)).all())
        self.assertEqual(len(graph), 1)
        self.assertEqual(graph[0]['no_programado']['inventarios'], 3)


    def test_inventory_search_finds_renamed_client_without_rewriting_source(self):
        from app.services.inventory_listing import listar_inventarios
        self.db.connection().exec_driver_sql('CREATE TABLE inventario_cierres (inventario_id INTEGER PRIMARY KEY, mes_cierre DATE)')
        original = self.customer()
        api.modificar_cliente(original['id'], ClienteEntrada(nombre='Acme Argentina'))
        result = listar_inventarios(self.db, buscar='Acme Argentina', vista='TODOS')
        self.assertEqual(result['total'], 2)
        self.assertTrue(all(row['cliente_nombre'] == 'Acme Argentina' for row in result['inventarios']))
        self.assertEqual(set(self.db.scalars(select(Inventario.cliente))), {'Acme SA', ' ACME SA '})
