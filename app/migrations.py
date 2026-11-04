from sqlalchemy import inspect, text

from app.database import engine


COLUMNAS_NUEVAS = {
    "causas_diferencia": {
        "categoria": "VARCHAR(30) NOT NULL DEFAULT 'OTRA'",
    },
    "plantillas": {
        "categoria": "VARCHAR(30) NOT NULL DEFAULT 'PIEZAS'",
        "tipo_conteo": "VARCHAR(30) NOT NULL DEFAULT 'GLOBAL'",
        "formato_impresion": (
            "VARCHAR(40) NOT NULL DEFAULT 'FLUJO_HORIZONTAL'"
        ),
        "controla_remitos": "BOOLEAN NOT NULL DEFAULT 0",
        "actualizada_en": "DATETIME NULL",
        "tipo_inventario_codigo": (
            "VARCHAR(50) NOT NULL DEFAULT 'PIEZAS_PROCESO'"
        ),
    },
    "inventarios": {
        "origen": "VARCHAR(20) NOT NULL DEFAULT 'PLANTILLA'",
        "categoria": "VARCHAR(30) NOT NULL DEFAULT 'PIEZAS'",
        "modalidad_conteo": (
            "VARCHAR(20) NOT NULL DEFAULT 'ESTANDAR'"
        ),
        "formato_impresion": (
            "VARCHAR(40) NOT NULL DEFAULT 'FLUJO_HORIZONTAL'"
        ),
        "formato_version_id": "INTEGER NULL",
        "programacion_id": "INTEGER NULL",
        "fecha_programada": "DATE NULL",
        "stock_actualizado_en": "DATETIME NULL",
        "stock_origen": (
            "VARCHAR(30) NOT NULL DEFAULT 'BASE_PRODUCTIVA'"
        ),
        "controla_remitos": "BOOLEAN NOT NULL DEFAULT 0",
        "ultimo_remito_ingreso": "VARCHAR(80) NOT NULL DEFAULT ''",
        "ultimo_remito_egreso": "VARCHAR(80) NOT NULL DEFAULT ''",
        "colaboradores": "VARCHAR(1000) NOT NULL DEFAULT ''",
        "ambito": "VARCHAR(20) NOT NULL DEFAULT 'INTERNO'",
        "tipo_inventario_codigo": (
            "VARCHAR(50) NOT NULL DEFAULT 'PIEZAS_PROCESO'"
        ),
    },
    "programaciones_inventario": {
        "colaboradores": "VARCHAR(1000) NOT NULL DEFAULT ''",
    },
    "formato_versiones": {
        "nombre": "VARCHAR(120) NULL",
    },
    "plantilla_items": {
        "codigo_cliente": "VARCHAR(80) NOT NULL DEFAULT ''",
        "codigo_material": "VARCHAR(80) NOT NULL DEFAULT ''",
        "diametro": "VARCHAR(40) NOT NULL DEFAULT ''",
        "largo": "VARCHAR(40) NOT NULL DEFAULT ''",
        "espesor": "VARCHAR(40) NOT NULL DEFAULT ''",
        "unidad": "VARCHAR(20) NOT NULL DEFAULT ''",
        "contar_material": "BOOLEAN NOT NULL DEFAULT 1",
        "tipo_estructura": (
            "VARCHAR(20) NOT NULL DEFAULT 'INDEPENDIENTE'"
        ),
    },
    "inventario_items": {
        "codigo_cliente": "VARCHAR(80) NOT NULL DEFAULT ''",
        "codigo_material": "VARCHAR(80) NOT NULL DEFAULT ''",
        "diametro": "VARCHAR(40) NOT NULL DEFAULT ''",
        "largo": "VARCHAR(40) NOT NULL DEFAULT ''",
        "espesor": "VARCHAR(40) NOT NULL DEFAULT ''",
        "unidad": "VARCHAR(20) NOT NULL DEFAULT ''",
        "lote": "VARCHAR(80) NOT NULL DEFAULT ''",
        "codigo_padre": "VARCHAR(80) NOT NULL DEFAULT ''",
        "nivel": "INTEGER NOT NULL DEFAULT 0",
        "uso": "DOUBLE NOT NULL DEFAULT 1",
        "ruta": "VARCHAR(2000) NOT NULL DEFAULT ''",
        "tipo_estructura": (
            "VARCHAR(20) NOT NULL DEFAULT 'INDEPENDIENTE'"
        ),
        "etapa": "VARCHAR(30) NOT NULL DEFAULT 'TERMINADO'",
        "operacion": "VARCHAR(50) NOT NULL DEFAULT ''",
        "titulo_operacion": "VARCHAR(150) NOT NULL DEFAULT ''",
        "proveedor": "VARCHAR(100) NOT NULL DEFAULT ''",
        "stock_pendiente": "BOOLEAN NOT NULL DEFAULT 0",
        "stock_asignado": "DOUBLE NOT NULL DEFAULT 0",
        "conteo_vacios": "DOUBLE NULL",
        "conteo_llenos": "DOUBLE NULL",
        "conteo_rotos": "DOUBLE NULL",
        "contar_material": "BOOLEAN NOT NULL DEFAULT 1",
        "causa_diferencia_codigo": "VARCHAR(50) NULL",
        "ajustado_sistema": "BOOLEAN NOT NULL DEFAULT 0",
        "ajustado_sistema_en": "DATETIME NULL",
        "observaciones": "VARCHAR(1000) NOT NULL DEFAULT ''",
    },
    "conciliacion_items": {
        "detalle_inicial": "VARCHAR(4000) NOT NULL DEFAULT ''",
        "detalle_final": "VARCHAR(4000) NOT NULL DEFAULT ''",
    },
}


def aplicar_migraciones_simples() -> None:
    """
    Agrega las columnas de esta versión sin borrar los inventarios existentes.

    Es intencionalmente acotado: para cambios estructurales más complejos
    incorporaremos Alembic.
    """
    inspector = inspect(engine)
    tablas = set(inspector.get_table_names())

    with engine.begin() as conexion:
        for tabla, columnas in COLUMNAS_NUEVAS.items():
            if tabla not in tablas:
                continue
            existentes = {
                columna["name"]
                for columna in inspector.get_columns(tabla)
            }
            for nombre, definicion in columnas.items():
                if nombre in existentes:
                    continue
                conexion.execute(
                    text(
                        f"ALTER TABLE `{tabla}` "
                        f"ADD COLUMN `{nombre}` {definicion}"
                    )
                )
        if "plantillas" in tablas:
            conexion.execute(
                text(
                    "UPDATE plantillas "
                    "SET tipo_inventario_codigo = 'MATERIA_PRIMA' "
                    "WHERE categoria = 'MATERIA_PRIMA' "
                    "AND tipo_inventario_codigo = 'PIEZAS_PROCESO'"
                )
            )
        if "inventarios" in tablas:
            conexion.execute(
                text(
                    "UPDATE inventarios "
                    "SET tipo_inventario_codigo = CASE "
                    "WHEN categoria = 'CICLICO' THEN 'CICLICO' "
                    "WHEN categoria = 'MATERIA_PRIMA' THEN 'MATERIA_PRIMA' "
                    "WHEN modalidad_conteo = 'MEDIOS' THEN 'MEDIOS' "
                    "ELSE tipo_inventario_codigo END "
                    "WHERE tipo_inventario_codigo = 'PIEZAS_PROCESO'"
                )
            )
