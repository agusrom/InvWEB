"""Persistencia SQLite del mapa de depósito y sus ubicaciones."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from app.config import BASE_DIR


DATABASE_PATH = BASE_DIR / "data" / "deposito.db"


def conectar() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(DATABASE_PATH, timeout=20)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.execute("PRAGMA journal_mode = WAL")
    conexion.execute("PRAGMA busy_timeout = 20000")
    return conexion


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def inicializar_deposito() -> None:
    """Crea el SQLite y una estantería inicial sin tocar MySQL."""
    with conectar() as conexion:
        conexion.executescript(
            """
            CREATE TABLE IF NOT EXISTS estanterias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                sector TEXT NOT NULL DEFAULT '',
                columnas INTEGER NOT NULL,
                activa INTEGER NOT NULL DEFAULT 1,
                creado_en TEXT NOT NULL,
                actualizado_en TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS niveles (
                estanteria_id INTEGER NOT NULL,
                numero INTEGER NOT NULL,
                tipo TEXT NOT NULL CHECK (
                    tipo IN ('PALLET', 'BANDEJA', 'CAJA', 'PERSONALIZADO')
                ),
                filas INTEGER NOT NULL DEFAULT 1,
                divisiones INTEGER NOT NULL DEFAULT 2,
                PRIMARY KEY (estanteria_id, numero),
                FOREIGN KEY (estanteria_id) REFERENCES estanterias(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS ubicaciones (
                estanteria_id INTEGER NOT NULL,
                nivel INTEGER NOT NULL,
                columna INTEGER NOT NULL,
                fila INTEGER NOT NULL,
                posicion INTEGER NOT NULL,
                tipo_articulo TEXT NOT NULL CHECK (
                    tipo_articulo IN ('PIEZA', 'MATERIA_PRIMA')
                ),
                codigo TEXT NOT NULL,
                descripcion TEXT NOT NULL DEFAULT '',
                codigo_cliente TEXT NOT NULL DEFAULT '',
                trazabilidad TEXT NOT NULL,
                cantidad REAL NOT NULL,
                estado TEXT NOT NULL DEFAULT 'CONFIRMADA' CHECK (
                    estado IN ('CONFIRMADA', 'VERIFICAR')
                ),
                actualizado_en TEXT NOT NULL,
                PRIMARY KEY (
                    estanteria_id, nivel, columna, fila, posicion
                ),
                FOREIGN KEY (estanteria_id) REFERENCES estanterias(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS ix_ubicaciones_codigo
                ON ubicaciones(codigo);
            CREATE INDEX IF NOT EXISTS ix_ubicaciones_trazabilidad
                ON ubicaciones(trazabilidad);
            """
        )
        ahora = _ahora()
        conexion.execute(
            """
            INSERT OR IGNORE INTO estanterias (
                codigo, nombre, sector, columnas, activa,
                creado_en, actualizado_en
            ) VALUES ('A-01', 'Estantería A-01', 'Sector A', 4, 1, ?, ?)
            """,
            (ahora, ahora),
        )
        fila = conexion.execute(
            "SELECT id FROM estanterias WHERE codigo = 'A-01'"
        ).fetchone()
        niveles = (
            (1, "BANDEJA", 2, 4),
            (2, "CAJA", 2, 4),
            (3, "PALLET", 1, 2),
            (4, "PALLET", 1, 3),
            (5, "PALLET", 1, 3),
        )
        conexion.executemany(
            """
            INSERT OR IGNORE INTO niveles (
                estanteria_id, numero, tipo, filas, divisiones
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [(fila["id"], *nivel) for nivel in niveles],
        )


def _estanteria_dict(fila) -> dict:
    datos = dict(fila)
    return {
        "id": int(datos["id"]),
        "codigo": datos["codigo"],
        "nombre": datos["nombre"],
        "sector": datos["sector"],
        "columnas": int(datos["columnas"]),
        "activa": bool(datos["activa"]),
        "ocupadas": int(datos.get("ocupadas", 0) or 0),
        "cantidad_total": float(datos.get("cantidad_total", 0) or 0),
    }


def listar_estanterias() -> list[dict]:
    with conectar() as conexion:
        filas = conexion.execute(
            """
            SELECT e.id, e.codigo, e.nombre, e.sector, e.columnas, e.activa,
                   COUNT(u.codigo) AS ocupadas,
                   COALESCE(SUM(u.cantidad), 0) AS cantidad_total
            FROM estanterias e
            LEFT JOIN ubicaciones u ON u.estanteria_id = e.id
            GROUP BY e.id, e.codigo, e.nombre, e.sector, e.columnas, e.activa
            ORDER BY e.sector, e.codigo
            """
        ).fetchall()
    return [_estanteria_dict(fila) for fila in filas]


def obtener_estanteria(codigo: str) -> dict | None:
    codigo = codigo.strip().upper()
    with conectar() as conexion:
        fila = conexion.execute(
            """
            SELECT id, codigo, nombre, sector, columnas, activa
            FROM estanterias WHERE codigo = ?
            """,
            (codigo,),
        ).fetchone()
        if fila is None:
            return None
        niveles = conexion.execute(
            """
            SELECT numero, tipo, filas, divisiones
            FROM niveles WHERE estanteria_id = ? ORDER BY numero
            """,
            (fila["id"],),
        ).fetchall()
        ubicaciones = conexion.execute(
            """
            SELECT nivel, columna, fila, posicion, tipo_articulo, codigo,
                   descripcion, codigo_cliente, trazabilidad, cantidad, estado,
                   actualizado_en
            FROM ubicaciones
            WHERE estanteria_id = ?
            ORDER BY nivel, columna, fila, posicion
            """,
            (fila["id"],),
        ).fetchall()
    resultado = _estanteria_dict(fila)
    resultado["niveles"] = [
        {
            "numero": int(nivel["numero"]),
            "tipo": nivel["tipo"],
            "filas": int(nivel["filas"]),
            "divisiones": int(nivel["divisiones"]),
        }
        for nivel in niveles
    ]
    resultado["ubicaciones"] = [dict(ubicacion) for ubicacion in ubicaciones]
    return resultado


def _coordenadas_validas(datos: dict) -> set[tuple[int, int, int, int]]:
    return {
        (nivel["numero"], columna, fila, posicion)
        for nivel in datos["niveles"]
        for columna in range(1, datos["columnas"] + 1)
        for fila in range(1, nivel["filas"] + 1)
        for posicion in range(1, nivel["divisiones"] + 1)
    }


def guardar_estanteria(codigo: str, datos: dict) -> dict:
    codigo = codigo.strip().upper()
    numeros = [nivel["numero"] for nivel in datos["niveles"]]
    if len(numeros) != len(set(numeros)):
        raise ValueError("No se puede repetir el número de piso")
    validas = _coordenadas_validas(datos)
    with conectar() as conexion:
        existente = conexion.execute(
            "SELECT id FROM estanterias WHERE codigo = ?",
            (codigo,),
        ).fetchone()
        ahora = _ahora()
        if existente:
            estanteria_id = int(existente["id"])
            ocupadas = conexion.execute(
                """
                SELECT nivel, columna, fila, posicion
                FROM ubicaciones WHERE estanteria_id = ?
                """,
                (estanteria_id,),
            ).fetchall()
            invalidas = [
                (
                    int(item["nivel"]), int(item["columna"]),
                    int(item["fila"]), int(item["posicion"]),
                )
                for item in ocupadas
                if (
                    int(item["nivel"]), int(item["columna"]),
                    int(item["fila"]), int(item["posicion"]),
                ) not in validas
            ]
            if invalidas:
                raise ValueError(
                    "La nueva distribución eliminaría ubicaciones ocupadas. "
                    "Mové o vaciá esas posiciones antes de reducir el tamaño."
                )
            conexion.execute(
                """
                UPDATE estanterias
                SET nombre = ?, sector = ?, columnas = ?, actualizado_en = ?
                WHERE id = ?
                """,
                (
                    datos["nombre"], datos["sector"], datos["columnas"],
                    ahora, estanteria_id,
                ),
            )
            conexion.execute(
                "DELETE FROM niveles WHERE estanteria_id = ?",
                (estanteria_id,),
            )
        else:
            cursor = conexion.execute(
                """
                INSERT INTO estanterias (
                    codigo, nombre, sector, columnas, activa,
                    creado_en, actualizado_en
                ) VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    codigo, datos["nombre"], datos["sector"],
                    datos["columnas"], ahora, ahora,
                ),
            )
            estanteria_id = int(cursor.lastrowid)
        conexion.executemany(
            """
            INSERT INTO niveles (
                estanteria_id, numero, tipo, filas, divisiones
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    estanteria_id, nivel["numero"], nivel["tipo"],
                    nivel["filas"], nivel["divisiones"],
                )
                for nivel in datos["niveles"]
            ],
        )
    return obtener_estanteria(codigo)


def guardar_ubicacion(
    codigo_estanteria: str,
    nivel: int,
    columna: int,
    fila: int,
    posicion: int,
    datos: dict,
) -> dict:
    estanteria = obtener_estanteria(codigo_estanteria)
    if estanteria is None:
        raise LookupError("Estantería no encontrada")
    configuracion = next(
        (item for item in estanteria["niveles"] if item["numero"] == nivel),
        None,
    )
    if (
        configuracion is None
        or columna < 1 or columna > estanteria["columnas"]
        or fila < 1 or fila > configuracion["filas"]
        or posicion < 1 or posicion > configuracion["divisiones"]
    ):
        raise ValueError("La ubicación no existe en la distribución actual")
    with conectar() as conexion:
        conexion.execute(
            """
            INSERT INTO ubicaciones (
                estanteria_id, nivel, columna, fila, posicion, tipo_articulo,
                codigo, descripcion, codigo_cliente, trazabilidad, cantidad,
                estado, actualizado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(estanteria_id, nivel, columna, fila, posicion)
            DO UPDATE SET
                tipo_articulo = excluded.tipo_articulo,
                codigo = excluded.codigo,
                descripcion = excluded.descripcion,
                codigo_cliente = excluded.codigo_cliente,
                trazabilidad = excluded.trazabilidad,
                cantidad = excluded.cantidad,
                estado = excluded.estado,
                actualizado_en = excluded.actualizado_en
            """,
            (
                estanteria["id"], nivel, columna, fila, posicion,
                datos["tipo_articulo"], datos["codigo"], datos["descripcion"],
                datos.get("codigo_cliente", ""), datos["trazabilidad"],
                datos["cantidad"], datos["estado"], _ahora(),
            ),
        )
    return obtener_estanteria(codigo_estanteria)


def eliminar_ubicacion(
    codigo_estanteria: str,
    nivel: int,
    columna: int,
    fila: int,
    posicion: int,
) -> bool:
    estanteria = obtener_estanteria(codigo_estanteria)
    if estanteria is None:
        return False
    with conectar() as conexion:
        cursor = conexion.execute(
            """
            DELETE FROM ubicaciones
            WHERE estanteria_id = ? AND nivel = ? AND columna = ?
              AND fila = ? AND posicion = ?
            """,
            (estanteria["id"], nivel, columna, fila, posicion),
        )
        return cursor.rowcount > 0
