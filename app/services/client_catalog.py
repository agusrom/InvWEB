"""Identidad de cliente independiente del texto histórico de los inventarios."""
from functools import lru_cache
from datetime import datetime
import hashlib
import unicodedata
from uuid import uuid4
from sqlalchemy import func, select
from fastapi import HTTPException
from app import catalog_database as store
from app.catalog_database import Cliente, ClienteNombre
from app.models import Inventario, Plantilla


def clave_nombre(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    return ' '.join(''.join(c for c in value if not unicodedata.combining(c)).casefold().split())


def clave_alias(value):
    # Identidad normalizada con índice corto y portable a MySQL.
    return hashlib.sha256(clave_nombre(value).encode('utf-8')).hexdigest()


def _alias(db, cliente, value):
    value = ' '.join(str(value).split())
    key = clave_alias(value)
    if not clave_nombre(value) or len(value) > 120:
        raise HTTPException(status_code=422, detail='Ingresá un nombre de cliente de hasta 120 caracteres')
    entry = db.get(ClienteNombre, key)
    if entry and entry.cliente_id != cliente.id:
        raise HTTPException(status_code=409, detail=f'El nombre «{value}» pertenece a otro cliente. Usá Unificar clientes si representan al mismo.')
    if entry:
        entry.valores = sorted(set(entry.valores + [value]))
    else:
        db.add(ClienteNombre(clave=key, cliente_id=cliente.id, valores=[value]))


def importar_clientes(source):
    # Solo cabeceras distintas; no se leen ítems ni se reescribe la fuente.
    names = set(source.scalars(select(Inventario.cliente).distinct()).all())
    names.update(source.scalars(select(Plantilla.cliente).distinct()).all())
    with store.session() as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        for raw in sorted(names):
            if not clave_nombre(raw):
                continue
            entry = db.get(ClienteNombre, clave_alias(raw))
            cliente = db.get(Cliente, entry.cliente_id) if entry else None
            if cliente is None:
                name = ' '.join(raw.split())
                cliente = Cliente(codigo='CLI-' + uuid4().hex[:12].upper(), nombre=name, valor=name)
                db.add(cliente); db.flush()
            _alias(db, cliente, raw)
            # SQL debe poder encontrar también el texto histórico exacto.
            entry = db.get(ClienteNombre, clave_alias(raw))
            if raw not in entry.valores:
                entry.valores = entry.valores + [raw]
        if db.get(store.CatalogMeta, "clientes_importados_en") is None:
            db.add(store.CatalogMeta(clave="clientes_importados_en", valor=datetime.now().astimezone().isoformat()))
        db.commit()
    _snapshot.cache_clear()


def _revision():
    path = store.DATABASE_PATH.resolve()
    return str(path), tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in (path, path.with_name(path.name + '-wal')))


@lru_cache(maxsize=8)
def _snapshot(path, revision):
    del path, revision
    with store.session() as db:
        clients = {c.id: dict(cliente_id=c.id, cliente_codigo=c.codigo, cliente_nombre=c.nombre,
                    cliente_valor=c.valor, cliente_activo=c.activo and c.reemplazado_por_id is None) for c in db.scalars(select(Cliente)).all()}
        return {entry.clave: dict(clients[entry.cliente_id], aliases=entry.valores)
                for entry in db.scalars(select(ClienteNombre)).all() if entry.cliente_id in clients}


def referencia(nombre):
    record = _snapshot(*_revision()).get(clave_alias(nombre))
    return {k: v for k, v in record.items() if k != 'aliases'} if record else dict(cliente_id=None, cliente_codigo='', cliente_nombre=nombre, cliente_valor=nombre, cliente_activo=False)


def nombres_equivalentes(nombre):
    data = _snapshot(*_revision())
    current = data.get(clave_alias(nombre))
    if not current:
        return [nombre]
    names = {nombre, current['cliente_valor'], current['cliente_nombre']}
    for item in data.values():
        if item['cliente_id'] == current['cliente_id']:
            names.update(item['aliases'])
    return sorted(names)


def valor_cliente(nombre, anterior=None):
    ref = referencia(nombre)
    if ref['cliente_id'] is None:
        raise HTTPException(status_code=422, detail='Seleccioná un cliente del catálogo. Podés agregarlo en Configuración → Catálogos.')
    unchanged = anterior is not None and referencia(anterior)['cliente_id'] == ref['cliente_id']
    if not ref['cliente_activo'] and not unchanged:
        raise HTTPException(status_code=422, detail='El cliente está inactivo; no está disponible para nuevas asignaciones')
    return ref['cliente_valor']


def usos(source):
    counts = {}
    for model, kind in ((Inventario, 'inventarios'), (Plantilla, 'plantillas')):
        for name, count in source.execute(select(model.cliente, func.count()).group_by(model.cliente)):
            cid = referencia(name)['cliente_id']
            if cid:
                counts.setdefault(cid, {'inventarios': 0, 'plantillas': 0})[kind] += count
    return counts


def cliente_dict(db, client, usage=None):
    aliases = [v for entry in db.scalars(select(ClienteNombre).where(ClienteNombre.cliente_id == client.id)).all() for v in entry.valores]
    return dict(id=client.id, codigo=client.codigo, nombre=client.nombre, valor=client.valor,
                descripcion=client.descripcion, orden=client.orden, activo=client.activo,
                reemplazado_por_id=client.reemplazado_por_id, aliases=sorted(set(aliases)),
                **(usage or {'inventarios': 0, 'plantillas': 0}))


def listar(source=None):
    usage = usos(source) if source is not None else {}
    with store.session() as db:
        return [cliente_dict(db, c, usage.get(c.id)) for c in db.scalars(select(Cliente).order_by(Cliente.orden, Cliente.nombre)).all()]


def guardar(payload, client_id=None):
    with store.session() as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        client = db.get(Cliente, client_id) if client_id else None
        if client_id and client is None:
            raise HTTPException(status_code=404, detail='Cliente no encontrado')
        if client and client.reemplazado_por_id:
            raise HTTPException(status_code=409, detail='Este cliente ya fue unificado; editá el cliente de destino')
        name = ' '.join(payload['nombre'].split())
        if not name:
            raise HTTPException(status_code=422, detail='Ingresá el nombre del cliente')
        owner = db.get(ClienteNombre, clave_alias(name))
        if owner and (client is None or owner.cliente_id != client.id):
            raise HTTPException(status_code=409, detail='Ya existe un cliente con ese nombre o nombre asociado')
        if client is None:
            client = Cliente(codigo='CLI-' + uuid4().hex[:12].upper(), nombre=name, valor=name)
            db.add(client); db.flush()
        # Los nombres anteriores siempre se conservan para resolver el historial.
        for alias in [client.valor, client.nombre, name, *payload.get('aliases', [])]:
            _alias(db, client, alias)
        client.nombre = name
        client.descripcion = payload.get('descripcion', '').strip()
        client.activo = payload.get('activo', True)
        client.orden = payload.get('orden', 100)
        db.flush()
        result = cliente_dict(db, client)
        db.commit()
    _snapshot.cache_clear()
    return result


def unificar(origen, destino):
    if origen == destino:
        raise HTTPException(status_code=422, detail='Elegí dos clientes distintos')
    with store.session() as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        source, target = db.get(Cliente, origen), db.get(Cliente, destino)
        if not source or not target:
            raise HTTPException(status_code=404, detail='Cliente no encontrado')
        if source.reemplazado_por_id or target.reemplazado_por_id or not target.activo:
            raise HTTPException(status_code=409, detail='Elegí clientes sin unificar y un destino activo')
        for entry in db.scalars(select(ClienteNombre).where(ClienteNombre.cliente_id == origen)).all():
            entry.cliente_id = destino
        # También redirige las identidades ya unificadas hacia el origen.
        for entry in db.scalars(select(Cliente).where(Cliente.reemplazado_por_id == origen)).all():
            entry.reemplazado_por_id = destino
        source.reemplazado_por_id = destino
        source.activo = False
        db.commit()
    _snapshot.cache_clear()
    return {'ok': True}


def eliminar(client_id, source):
    usage = usos(source).get(client_id, {})
    with store.session() as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        client = db.get(Cliente, client_id)
        if not client:
            raise HTTPException(status_code=404, detail='Cliente no encontrado')
        if any(usage.values()) or client.reemplazado_por_id or db.scalar(select(Cliente.id).where(Cliente.reemplazado_por_id == client_id)):
            raise HTTPException(status_code=409, detail='El cliente tiene historial o identidades asociadas. Usá Desactivar para conservarlos.')
        for row in db.scalars(select(ClienteNombre).where(ClienteNombre.cliente_id == client_id)).all():
            db.delete(row)
        db.flush()
        db.delete(client); db.commit()
    _snapshot.cache_clear()


def nombres_para_busqueda(termino):
    """Busca por nombre visible o asociado y devuelve textos que aún guarda MySQL."""
    text = clave_nombre(termino)
    if not text:
        return []
    data = _snapshot(*_revision())
    matched = {entry['cliente_id'] for entry in data.values()
               if text in clave_nombre(entry['cliente_nombre'])
               or any(text in clave_nombre(alias) for alias in entry['aliases'])}
    names = set()
    for entry in data.values():
        if entry['cliente_id'] in matched:
            names.update(entry['aliases'])
            names.add(entry['cliente_valor'])
    return sorted(names)
