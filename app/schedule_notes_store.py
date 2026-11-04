"""Notas del cronograma en SQLite, independientes de la base MySQL."""
from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3

STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "notas_cronograma.db"


@contextmanager
def connection():
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(STORE_PATH, timeout=30)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("""CREATE TABLE IF NOT EXISTS notas_cronograma (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            titulo TEXT NOT NULL,
            contenido TEXT NOT NULL DEFAULT '',
            cerrada INTEGER NOT NULL DEFAULT 0,
            creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            actualizada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS ix_notas_cronograma_fecha ON notas_cronograma(fecha)")
        yield db


def nota_dict(row):
    return {
        "id": row["id"], "fecha": row["fecha"], "titulo": row["titulo"],
        "contenido": row["contenido"], "cerrada": bool(row["cerrada"]),
    }


def listar_notas():
    with connection() as db:
        return [nota_dict(row) for row in db.execute(
            "SELECT * FROM notas_cronograma ORDER BY fecha, id"
        )]


def guardar_nota(datos, nota_id=None):
    values = (datos.fecha.isoformat(), datos.titulo.strip(), datos.contenido, int(datos.cerrada))
    with connection() as db:
        if nota_id is None:
            cursor = db.execute(
                "INSERT INTO notas_cronograma (fecha, titulo, contenido, cerrada) VALUES (?, ?, ?, ?)",
                values,
            )
            nota_id = cursor.lastrowid
        else:
            cursor = db.execute(
                """UPDATE notas_cronograma SET fecha=?, titulo=?, contenido=?, cerrada=?,
                   actualizada_en=CURRENT_TIMESTAMP WHERE id=?""", (*values, nota_id),
            )
            if cursor.rowcount == 0:
                return None
        return nota_dict(db.execute("SELECT * FROM notas_cronograma WHERE id=?", (nota_id,)).fetchone())


def eliminar_nota(nota_id: int) -> bool:
    with connection() as db:
        return db.execute(
            "DELETE FROM notas_cronograma WHERE id = ?", (nota_id,),
        ).rowcount > 0
