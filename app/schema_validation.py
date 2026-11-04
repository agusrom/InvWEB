"""Validacion de solo lectura para el esquema MySQL del servidor."""

from sqlalchemy import inspect

from app.database import Base, engine


TABLAS_AUXILIARES = {
    "inventario_cierres",
    "programacion_cierres",
    "inventario_programaciones",
    "conteo_cajas",
    "conteo_bases",
    "conteo_revisiones",
    "conciliacion_remitos",
    "conciliacion_remito_items",
    "conciliacion_ingresos_control",
    "conciliacion_egresos_control",
    "conciliacion_items_excluidos",
    "inventarios_relaciones",
}


def validar_esquema_mysql() -> None:
    """Comprueba tablas y columnas sin ejecutar CREATE, ALTER ni DROP."""
    if not engine.dialect.name.startswith("mysql"):
        raise RuntimeError("DATABASE_URL debe apuntar a MySQL.")
    inspector = inspect(engine)
    existentes = set(inspector.get_table_names())
    requeridas = set(Base.metadata.tables) | TABLAS_AUXILIARES
    faltantes = sorted(requeridas - existentes)
    errores = []
    if faltantes:
        errores.append("Tablas faltantes: " + ", ".join(faltantes))
    for nombre, tabla in Base.metadata.tables.items():
        if nombre not in existentes:
            continue
        columnas = {columna["name"] for columna in inspector.get_columns(nombre)}
        faltan = sorted({columna.name for columna in tabla.columns} - columnas)
        if faltan:
            errores.append(f"{nombre}: faltan columnas {', '.join(faltan)}")
    if errores:
        raise RuntimeError(
            "El esquema MySQL no esta completo. La aplicacion no modifico la base. "
            + " | ".join(errores)
        )
