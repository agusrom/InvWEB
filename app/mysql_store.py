"""Pequeña capa DB-API para los almacenes auxiliares migrados a MySQL."""

from __future__ import annotations

import re

from app.database import engine


def _traducir(sql: str) -> str:
    sql = sql.replace("?", "%s")
    sql = re.sub(r"\bINSERT\s+OR\s+IGNORE\b", "INSERT IGNORE", sql, flags=re.I)
    sql = re.sub(r"\bBEGIN\s+IMMEDIATE\b", "START TRANSACTION", sql, flags=re.I)
    # UPSERTs simples usados por cierres, bases y revisiones.
    sql = re.sub(
        r"ON\s+CONFLICT\s*\([^)]+\)\s+DO\s+UPDATE\s+SET",
        "ON DUPLICATE KEY UPDATE",
        sql,
        flags=re.I,
    )
    sql = re.sub(
        r"excluded\.([A-Za-z0-9_]+)",
        lambda m: f"VALUES({m.group(1)})",
        sql,
        flags=re.I,
    )
    return sql


class Cursor:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        """Cantidad de filas afectadas, como en el cursor DB-API real."""
        return self._cursor.rowcount

    def _convertir(self, fila):
        if fila is None or isinstance(fila, dict):
            return fila
        nombres = [columna[0] for columna in self._cursor.description or ()]
        return Fila(zip(nombres, fila))

    def fetchone(self):
        return self._convertir(self._cursor.fetchone())

    def fetchall(self):
        return [self._convertir(fila) for fila in self._cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class Conexion:
    def __init__(self):
        self._conexion = engine.raw_connection()

    def execute(self, sql: str, parametros=()):
        cursor = self._conexion.cursor()
        cursor.execute(_traducir(sql), parametros)
        return Cursor(cursor)

    def commit(self):
        self._conexion.commit()

    def rollback(self):
        self._conexion.rollback()

    def close(self):
        self._conexion.close()

    def __enter__(self):
        return self

    def __exit__(self, tipo, valor, traceback):
        try:
            self.rollback() if tipo else self.commit()
        finally:
            self.close()


def conectar() -> Conexion:
    if not engine.dialect.name.startswith("mysql"):
        raise RuntimeError(
            "La v0.82.0 requiere que DATABASE_URL apunte a MySQL."
        )
    return Conexion()


class Fila(dict):
    """Fila compatible con acceso SQLite por nombre o posición."""

    def __getitem__(self, clave):
        if isinstance(clave, int):
            return tuple(self.values())[clave]
        return super().__getitem__(clave)
