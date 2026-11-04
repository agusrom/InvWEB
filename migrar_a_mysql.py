"""Verifica MySQL y copia los datos históricos desde SQLite.

Este proceso NO crea bases, tablas ni columnas. La estructura debe cargarse
previamente con ``estructura_mysql.sql`` por un usuario autorizado.
"""

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import MetaData, Table, create_engine, func, inspect, select
from sqlalchemy.engine import make_url

load_dotenv()

from app import db  # noqa: E402


VERSION_ESQUEMA = 47
DESCRIPCION_VERSION = (
    "Migración SQLite a MySQL con consolidación de claves equivalentes"
)


def argumentos():
    parser = argparse.ArgumentParser(
        description="Verifica MySQL y migra los datos del sistema DNC."
    )
    parser.add_argument("--origen", help="Archivo SQLite anterior a copiar.")
    parser.add_argument(
        "--solo-verificar", action="store_true",
        help="Verifica tablas y columnas sin escribir datos.",
    )
    parser.add_argument(
        "--reemplazar-datos", action="store_true",
        help="Borra los datos DNC actuales y los reemplaza por SQLite.",
    )
    parser.add_argument("--confirmar-reemplazo", default="")
    return parser.parse_args()


def url_mysql():
    valor = os.getenv("DATABASE_URL", "").strip()
    if not valor:
        raise RuntimeError("Falta DATABASE_URL en el archivo .env.")
    url = make_url(valor)
    if not url.drivername.startswith("mysql"):
        raise RuntimeError("DATABASE_URL debe usar mysql+pymysql.")
    if not url.database or not re.fullmatch(r"[A-Za-z0-9_]+", url.database):
        raise RuntimeError("El nombre de la base MySQL es inválido o está vacío.")
    return url


def verificar_estructura(engine):
    """Controla toda la estructura sin ejecutar CREATE ni ALTER."""
    inspector = inspect(engine)
    existentes = set(inspector.get_table_names())
    requeridas = {tabla.name: tabla for tabla in db.metadata.sorted_tables}
    faltantes = sorted(set(requeridas) - existentes)
    if faltantes:
        raise RuntimeError(
            "Faltan tablas en MySQL: "
            f"{', '.join(faltantes)}. Un administrador debe ejecutar "
            "estructura_mysql.sql."
        )

    columnas_faltantes = []
    for nombre, tabla in requeridas.items():
        columnas = {columna["name"] for columna in inspector.get_columns(nombre)}
        columnas_faltantes.extend(
            f"{nombre}.{columna.name}"
            for columna in tabla.columns
            if columna.name not in columnas
        )
    if columnas_faltantes:
        raise RuntimeError(
            "Faltan columnas en MySQL: "
            f"{', '.join(columnas_faltantes)}. El migrador no intentará crearlas."
        )
    return requeridas


def contar_tablas(engine, nombres=None):
    nombres = set(nombres or db.metadata.tables)
    resultado = {}
    with engine.connect() as conexion:
        for tabla in db.metadata.sorted_tables:
            if tabla.name not in nombres:
                continue
            resultado[tabla.name] = conexion.execute(
                select(func.count()).select_from(tabla)
            ).scalar_one()
    return resultado


def inspeccionar_sqlite(origen):
    ruta = Path(origen).expanduser().resolve()
    if not ruta.is_file():
        raise RuntimeError(f"No se encontró la base SQLite: {ruta}")
    if ruta.stat().st_size == 0:
        raise RuntimeError(f"El archivo SQLite está vacío: {ruta}")

    engine = create_engine(f"sqlite:///{ruta.as_posix()}")
    tablas = set(inspect(engine).get_table_names())
    tablas_utiles = tablas & set(db.metadata.tables)
    if not tablas_utiles:
        engine.dispose()
        raise RuntimeError(
            "El archivo seleccionado no contiene tablas reconocidas del sistema DNC."
        )
    conteos = contar_tablas(engine, tablas_utiles)
    if not any(conteos.values()):
        engine.dispose()
        raise RuntimeError("La base SQLite seleccionada no contiene registros.")
    return ruta, engine, tablas_utiles, conteos


def datos_operativos_en_destino(conteos):
    return {k: v for k, v in conteos.items() if k != "versiones_esquema" and v}


def vaciar_destino(conexion):
    """Elimina hijos antes que padres, respetando las claves foráneas."""
    for tabla in reversed(db.metadata.sorted_tables):
        conexion.execute(tabla.delete())


CLAVES_UNICAS = {
    "catalogos": [("tipo", "codigo")],
    "configuraciones": [("clave",)],
    "declaraciones": [("numero",)],
    "grupos_motivo": [("codigo",)],
    "piezas_control_logistica": [("codigo",)],
    "unidades_gestion": [("codigo",), ("nombre",)],
    "usuarios": [("usuario",)],
    "celulas": [("codigo",), ("nombre",), ("codigo_equipos",)],
    "motivos": [("codigo",)],
}

REFERENCIAS = {
    "celulas": {"unidad_gestion_id": "unidades_gestion"},
    "motivos": {"grupo_id": "grupos_motivo"},
    "declaracion_items": {
        "declaracion_id": "declaraciones",
        "motivo_id": "motivos",
    },
    "retrabajo_intervenciones": {
        "item_id": "declaracion_items",
        "motivo_scrap_id": "motivos",
    },
}


def clave_mysql(valor):
    """Aproxima la comparación de utf8mb4_unicode_ci de MySQL."""
    if valor is None:
        return None
    if not isinstance(valor, str):
        return valor
    normalizado = unicodedata.normalize("NFKD", valor.strip())
    sin_acentos = "".join(c for c in normalizado if not unicodedata.combining(c))
    return sin_acentos.casefold()


def deduplicar_filas(nombre, filas):
    """Combina claves que SQLite distingue pero MySQL considera iguales."""
    grupos_unicos = CLAVES_UNICAS.get(nombre, [])
    if not grupos_unicos or len(filas) < 2:
        return filas, {}, []

    padres = list(range(len(filas)))

    def buscar(i):
        while padres[i] != i:
            padres[i] = padres[padres[i]]
            i = padres[i]
        return i

    def unir(a, b):
        ra, rb = buscar(a), buscar(b)
        if ra != rb:
            padres[rb] = ra

    for columnas in grupos_unicos:
        vistos = {}
        for indice, fila in enumerate(filas):
            valores = tuple(clave_mysql(fila.get(columna)) for columna in columnas)
            # MySQL permite varias claves UNIQUE con NULL.
            if any(valor is None for valor in valores):
                continue
            if valores in vistos:
                unir(indice, vistos[valores])
            else:
                vistos[valores] = indice

    componentes = {}
    for indice in range(len(filas)):
        componentes.setdefault(buscar(indice), []).append(indice)

    mapa_ids = {}
    conflictos = []
    conservar = set()
    for indices in componentes.values():
        # Se conserva una fila activa antes que una inactiva; ante igualdad,
        # la de menor id para mantener referencias históricas estables.
        ganador = max(
            indices,
            key=lambda i: (
                bool(filas[i].get("activo", True)),
                -int(filas[i].get("id") or 0),
            ),
        )
        conservar.add(ganador)
        id_ganador = filas[ganador].get("id")
        for indice in indices:
            id_actual = filas[indice].get("id")
            if id_actual is not None and id_ganador is not None:
                mapa_ids[id_actual] = id_ganador
        if len(indices) > 1:
            conflictos.append(
                {
                    "tabla": nombre,
                    "conservado": id_ganador,
                    "combinados": [filas[i].get("id") for i in indices if i != ganador],
                }
            )
    return [fila for i, fila in enumerate(filas) if i in conservar], mapa_ids, conflictos


def preparar_datos(origen_engine, tablas_origen):
    """Carga, normaliza duplicados y actualiza referencias antes de insertar."""
    meta = MetaData()
    datos = {}
    with origen_engine.connect() as lectura:
        for tabla_destino in db.metadata.sorted_tables:
            nombre = tabla_destino.name
            if nombre not in tablas_origen or nombre == "versiones_esquema":
                continue
            tabla_origen = Table(nombre, meta, autoload_with=origen_engine)
            columnas_destino = {c.name for c in tabla_destino.columns}
            datos[nombre] = [
                {k: v for k, v in dict(fila).items() if k in columnas_destino}
                for fila in lectura.execute(select(tabla_origen)).mappings().all()
            ]

    mapas = {}
    conflictos = []
    for tabla_destino in db.metadata.sorted_tables:
        nombre = tabla_destino.name
        if nombre not in datos:
            continue
        for columna, padre in REFERENCIAS.get(nombre, {}).items():
            mapa = mapas.get(padre, {})
            if mapa:
                for fila in datos[nombre]:
                    if fila.get(columna) in mapa:
                        fila[columna] = mapa[fila[columna]]
        datos[nombre], mapas[nombre], nuevos = deduplicar_filas(nombre, datos[nombre])
        conflictos.extend(nuevos)
    return datos, conflictos


def copiar_sqlite(origen, destino, reemplazar=False):
    ruta, origen_engine, tablas_origen, conteos_origen = inspeccionar_sqlite(origen)
    conteos_antes = contar_tablas(destino)
    existentes = datos_operativos_en_destino(conteos_antes)
    if existentes and not reemplazar:
        detalle = ", ".join(f"{k}={v}" for k, v in existentes.items())
        origen_engine.dispose()
        raise RuntimeError(
            "MySQL ya contiene datos y no se sobrescribió nada: "
            f"{detalle}. Si son datos de prueba, usá la opción 3 del asistente."
        )

    datos_preparados, conflictos = preparar_datos(origen_engine, tablas_origen)
    copiados = {}
    try:
        with destino.begin() as escritura:
            if reemplazar:
                vaciar_destino(escritura)
            for tabla_destino in db.metadata.sorted_tables:
                nombre = tabla_destino.name
                if nombre not in datos_preparados:
                    continue
                datos = datos_preparados[nombre]
                if datos:
                    escritura.execute(tabla_destino.insert(), datos)
                copiados[nombre] = len(datos)
    finally:
        origen_engine.dispose()

    conteos_despues = contar_tablas(destino)
    errores = []
    for nombre, cantidad in copiados.items():
        if conteos_despues.get(nombre, 0) < cantidad:
            errores.append(
                f"{nombre}: SQLite={cantidad}, MySQL={conteos_despues.get(nombre, 0)}"
            )
    if errores:
        raise RuntimeError("La comprobación posterior no coincide: " + "; ".join(errores))
    return ruta, conteos_origen, copiados, conflictos


def registrar_version(engine):
    """Registra la migración sin volver a sembrar catálogos históricos."""
    tabla = db.metadata.tables["versiones_esquema"]
    with engine.begin() as conexion:
        existe = conexion.execute(
            select(func.count()).select_from(tabla).where(
                tabla.c.version == VERSION_ESQUEMA
            )
        ).scalar_one()
        if not existe:
            conexion.execute(
                tabla.insert().values(
                    version=VERSION_ESQUEMA,
                    descripcion=DESCRIPCION_VERSION,
                )
            )


def imprimir_conteos(titulo, conteos):
    print(titulo)
    for tabla, cantidad in conteos.items():
        print(f"  {tabla}: {cantidad} filas")


def imprimir_conflictos(conflictos):
    if not conflictos:
        return
    print("Claves equivalentes combinadas para compatibilidad con MySQL:")
    for conflicto in conflictos:
        ids = ", ".join(str(x) for x in conflicto["combinados"])
        print(
            f"  {conflicto['tabla']}: se conservó id={conflicto['conservado']} "
            f"y se combinaron id={ids}"
        )


def main():
    args = argumentos()
    if not args.solo_verificar and not args.origen:
        raise RuntimeError("Indicá --solo-verificar o --origen RUTA_ARCHIVO_DB.")
    if args.reemplazar_datos and args.confirmar_reemplazo != "REEMPLAZAR":
        raise RuntimeError(
            "Para reemplazar datos se requiere --confirmar-reemplazo REEMPLAZAR."
        )

    url = url_mysql()
    engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)
    try:
        verificar_estructura(engine)
        print("Estructura MySQL verificada. No se ejecutó CREATE ni ALTER.")
        if args.solo_verificar:
            imprimir_conteos("Registros actuales en MySQL:", contar_tablas(engine))
            return

        ruta, origen, copiados, conflictos = copiar_sqlite(
            args.origen, engine, reemplazar=args.reemplazar_datos
        )
        imprimir_conteos(f"Registros encontrados en SQLite ({ruta}):", origen)
        imprimir_conflictos(conflictos)
        imprimir_conteos("Registros copiados en esta ejecución:", copiados)
        registrar_version(engine)
        imprimir_conteos("Resultado final verificado en MySQL:", contar_tablas(engine))
        print("Migración terminada correctamente. Ya podés iniciar con run.bat.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
