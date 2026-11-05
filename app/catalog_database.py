"""Solo maestros nuevos en SQLite. Los catálogos existentes siguen en MySQL."""
from contextlib import contextmanager
from functools import lru_cache
import os
from pathlib import Path

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from app.config import BASE_DIR

DATABASE_PATH = Path(os.getenv('CATALOG_DATABASE_PATH', str(BASE_DIR / 'data' / 'catalogos.sqlite3')))


class LocalBase(DeclarativeBase):
    pass


class CatalogMeta(LocalBase):
    __tablename__ = 'catalogo_meta'
    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    valor: Mapped[str] = mapped_column(String(200), default='')


class Cliente(LocalBase):
    __tablename__ = 'clientes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    valor: Mapped[str] = mapped_column(String(120), unique=True)
    descripcion: Mapped[str] = mapped_column(String(255), default='')
    orden: Mapped[int] = mapped_column(Integer, default=100)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    reemplazado_por_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"), nullable=True)


class ClienteNombre(LocalBase):
    __tablename__ = 'cliente_nombres'
    clave: Mapped[str] = mapped_column(String(64), primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), index=True)
    valores: Mapped[list] = mapped_column(JSON)


@lru_cache(maxsize=8)
def _engine(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine('sqlite:///' + path, connect_args={'timeout': 30, 'check_same_thread': False})
    @event.listens_for(engine, 'connect')
    def pragmas(connection, _record):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=30000')
        connection.execute('PRAGMA journal_mode=WAL')
    # Exclusivamente tablas locales; nunca Base.metadata.create_all sobre MySQL.
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        LocalBase.metadata.create_all(connection)
        connection.commit()
    return engine


@contextmanager
def session():
    with Session(_engine(str(DATABASE_PATH.resolve())), expire_on_commit=False) as db:
        yield db

