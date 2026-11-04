"""Migra análisis locales y conciliaciones históricas al módulo unificado MySQL."""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from uuid import uuid5, NAMESPACE_URL

from sqlalchemy import Date, DateTime, MetaData, Table, inspect, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import selectinload


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import preconciliation_audit  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.local_reconciliation_store import (  # noqa: E402
    listar_codigos_excluidos,
    obtener_auditoria,
)
from app.models import Conciliacion  # noqa: E402
from app.preconciliation_store import guardar_nota  # noqa: E402
from app.routers.api import calcular_preconciliacion  # noqa: E402
from app.schemas import PreconciliacionCalculoEntrada  # noqa: E402


TABLAS_REQUERIDAS = {
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
    "analisis_stock",
    "analisis_stock_iniciales",
    "analisis_stock_auditoria",
    "analisis_stock_notas",
    "inventario_reconteos_legacy",
    "inventario_reconteo_items_legacy",
}
ARCHIVOS_LOCALES = (
    "conteo_cajas.db",
    "meses_cierre.db",
    "conciliacion_remitos.db",
    "relaciones_inventarios.db",
    "reconteos.db",
    "preconciliacion_auditoria.sqlite3",
    "preconciliacion_notas.json",
)

# El orden conserva las dependencias entre cabeceras y detalles. Los nombres
# de destino distintos se usan únicamente para preservar el reconteo
# experimental de v0.81.0 sin reactivarlo en la interfaz actual.
MIGRACIONES_SQLITE = (
    ("meses_cierre.db", "inventario_cierres", "inventario_cierres"),
    ("meses_cierre.db", "programacion_cierres", "programacion_cierres"),
    ("meses_cierre.db", "inventario_programaciones", "inventario_programaciones"),
    ("conteo_cajas.db", "conteo_bases", "conteo_bases"),
    ("conteo_cajas.db", "conteo_revisiones", "conteo_revisiones"),
    ("conteo_cajas.db", "conteo_cajas", "conteo_cajas"),
    ("conciliacion_remitos.db", "conciliacion_remitos", "conciliacion_remitos"),
    (
        "conciliacion_remitos.db",
        "conciliacion_remito_items",
        "conciliacion_remito_items",
    ),
    (
        "conciliacion_remitos.db",
        "conciliacion_ingresos_control",
        "conciliacion_ingresos_control",
    ),
    (
        "conciliacion_remitos.db",
        "conciliacion_egresos_control",
        "conciliacion_egresos_control",
    ),
    (
        "conciliacion_remitos.db",
        "conciliacion_items_excluidos",
        "conciliacion_items_excluidos",
    ),
    (
        "relaciones_inventarios.db",
        "inventarios_relaciones",
        "inventarios_relaciones",
    ),
    (
        "reconteos.db",
        "inventario_reconteos",
        "inventario_reconteos_legacy",
    ),
    (
        "reconteos.db",
        "inventario_reconteo_items",
        "inventario_reconteo_items_legacy",
    ),
)
ARCHIVOS_WMS = (
    "app/warehouse_store.py",
    "app/templates/warehouse.html",
    "app/static/css/warehouse.css",
    "app/static/js/warehouse.js",
    "data/deposito.db",
    "data/deposito.db-shm",
    "data/deposito.db-wal",
)


def serializable(valor):
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {str(clave): serializable(item) for clave, item in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [serializable(item) for item in valor]
    return valor


def fecha_mysql(valor) -> datetime:
    if isinstance(valor, datetime):
        return valor
    texto = str(valor or "").strip()
    if not texto:
        return datetime.now()
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return datetime.now()


def _convertir_valor_mysql(valor, tipo):
    """Convierte fechas SQLite a objetos aceptados por el dialecto MySQL."""
    if valor in (None, ""):
        return None if isinstance(tipo, (Date, DateTime)) else valor
    if isinstance(tipo, DateTime) and not isinstance(valor, datetime):
        try:
            return datetime.fromisoformat(str(valor))
        except ValueError:
            return valor
    if isinstance(tipo, Date) and not isinstance(valor, (date, datetime)):
        try:
            return date.fromisoformat(str(valor)[:10])
        except ValueError:
            return valor
    return valor


def importar_tabla_sqlite(
    ruta: Path,
    tabla_origen: str,
    tabla_destino: str,
    reporte: dict,
) -> None:
    """Copia una tabla local con UPSERT, conservando IDs e idempotencia."""
    if not ruta.exists():
        reporte["fuentes_ausentes"].append(str(ruta.relative_to(ROOT)))
        return
    with sqlite3.connect(ruta) as origen:
        origen.row_factory = sqlite3.Row
        existe = origen.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (tabla_origen,),
        ).fetchone()
        if not existe:
            reporte["fuentes_ausentes"].append(
                f"{ruta.relative_to(ROOT)}:{tabla_origen}"
            )
            return
        filas_origen = [dict(fila) for fila in origen.execute(
            f'SELECT * FROM "{tabla_origen}"'
        ).fetchall()]

    if not filas_origen:
        reporte["tablas_locales"][tabla_destino] = 0
        return

    tabla = Table(tabla_destino, MetaData(), autoload_with=engine)
    columnas = {columna.name: columna for columna in tabla.columns}
    filas = []
    for fila in filas_origen:
        filas.append({
            nombre: _convertir_valor_mysql(fila[nombre], columnas[nombre].type)
            for nombre in fila.keys() & columnas.keys()
        })

    sentencia = mysql_insert(tabla)
    claves_primarias = {columna.name for columna in tabla.primary_key.columns}
    actualizaciones = {
        columna.name: sentencia.inserted[columna.name]
        for columna in tabla.columns
        if columna.name not in claves_primarias
    }
    sentencia = (
        sentencia.on_duplicate_key_update(**actualizaciones)
        if actualizaciones
        else sentencia.prefix_with("IGNORE")
    )
    with engine.begin() as destino:
        # Lotes acotados para no superar el tamaño máximo de paquete del server.
        for inicio in range(0, len(filas), 500):
            destino.execute(sentencia, filas[inicio:inicio + 500])
    reporte["tablas_locales"][tabla_destino] = len(filas)


def importar_almacenes_locales(reporte: dict) -> None:
    for archivo, tabla_origen, tabla_destino in MIGRACIONES_SQLITE:
        importar_tabla_sqlite(
            ROOT / "data" / archivo,
            tabla_origen,
            tabla_destino,
            reporte,
        )


def validar_ids_bigint() -> list[str]:
    """Comprueba el esquema real que originó el error #1215."""
    inspector = inspect(engine)
    esperadas = (
        ("inventarios", "id"),
        ("inventario_items", "id"),
        ("programaciones_inventario", "id"),
        ("conciliaciones", "id"),
        ("conciliacion_items", "id"),
    )
    errores = []
    tablas = set(inspector.get_table_names())
    for tabla, columna in esperadas:
        if tabla not in tablas:
            errores.append(f"Falta la tabla principal {tabla}")
            continue
        definicion = next(
            (
                item for item in inspector.get_columns(tabla)
                if item["name"] == columna
            ),
            None,
        )
        tipo = str(definicion["type"]).upper() if definicion else ""
        if "BIGINT" not in tipo:
            errores.append(
                f"{tabla}.{columna} es {tipo or 'desconocido'}; "
                "el migrador v1.30 requiere BIGINT"
            )
    return errores


def clave_manual_legacy(conciliacion_id: int, clave: str) -> str:
    return "LEGACY-MANUAL-" + uuid5(
        NAMESPACE_URL,
        f"inventarios/conciliacion/{conciliacion_id}/{clave}",
    ).hex


def movimiento_legacy(conciliacion_id: int, tipo: str, fila: dict) -> dict:
    manual = bool(fila.get("manual"))
    cantidad_original = float(fila.get("cantidad_original", fila.get("cantidad", 0)) or 0)
    cantidad_actual = float(fila.get("cantidad", cantidad_original) or 0)
    cantidad_editada = (
        cantidad_actual
        if fila.get("cantidad_modificada") or manual
        else None
    )
    fecha = serializable(fila.get("fecha", ""))
    if tipo == "IN":
        codigo = str(fila.get("codigo_material") or fila.get("codigo") or "").strip().upper()
        identidad = {
            "codigo_material": codigo,
            "codigo": str(fila.get("codigo") or codigo),
            "remito": str(fila.get("remito") or ""),
            "fecha": fecha,
        }
    else:
        codigo = str(fila.get("codigo_pieza") or fila.get("pieza_origen") or "").strip().upper()
        identidad = {
            "pieza_origen": codigo,
            "remito": str(fila.get("remito") or ""),
            "fecha": fecha,
        }
    clave = (
        clave_manual_legacy(conciliacion_id, str(fila.get("movimiento_clave") or codigo))
        if manual
        else preconciliation_audit.source_key(tipo, identidad)
    )
    return {
        "clave": clave,
        "tipo": tipo,
        "remito": str(fila.get("remito") or ""),
        "fecha": fecha,
        "codigo": codigo,
        "cantidad_original": cantidad_original,
        "cantidad_editada": cantidad_editada,
        "verificado": bool(fila.get("verificado")),
        "observacion": str(fila.get("observacion") or ""),
        "manual": manual,
        "excluidos": [],
        "escenarios": [],
    }


def auditoria_legacy(conciliacion: Conciliacion) -> tuple[dict, dict]:
    anterior = obtener_auditoria(conciliacion.id)
    movimientos = {}
    for fila in anterior.get("remitos_ingreso", []):
        movimiento = movimiento_legacy(conciliacion.id, "IN", fila)
        movimientos[movimiento["clave"]] = movimiento
    for fila in anterior.get("remitos_egreso", []):
        movimiento = movimiento_legacy(conciliacion.id, "OUT", fila)
        movimientos[movimiento["clave"]] = movimiento

    items_por_id = {int(item.id): item.codigo for item in conciliacion.items}
    scrap = {}
    for item_id, detalle in anterior.get("items", {}).items():
        codigo = items_por_id.get(int(item_id))
        cantidad = float(detalle.get("scrap", 0) or 0)
        if codigo and cantidad:
            scrap[codigo] = cantidad
    excluidos = sorted(listar_codigos_excluidos(conciliacion.id))
    convertido = {
        "movimientos": movimientos,
        "scrap": {str(conciliacion.inventario_inicial_id): scrap},
        "codigos_excluidos": {
            str(conciliacion.inventario_inicial_id): excluidos,
        },
    }
    return convertido, serializable(anterior)


def importar_conciliaciones_legacy(respaldo: Path, reporte: dict) -> None:
    instantaneas = []
    with SessionLocal() as db:
        conciliaciones = db.scalars(
            select(Conciliacion)
            .options(selectinload(Conciliacion.items))
            .order_by(Conciliacion.creada_en, Conciliacion.id)
        ).unique().all()
        reporte["conciliaciones_detectadas"] = len(conciliaciones)
        for conciliacion in conciliaciones:
            auditoria, auditoria_original = auditoria_legacy(conciliacion)
            instantaneas.append({
                "conciliacion": {
                    "id": conciliacion.id,
                    "codigo": conciliacion.codigo,
                    "nombre": conciliacion.nombre,
                    "inventario_inicial_id": conciliacion.inventario_inicial_id,
                    "inventario_final_id": conciliacion.inventario_final_id,
                    "creada_en": serializable(conciliacion.creada_en),
                    "items": [
                        {
                            "codigo": item.codigo,
                            "stock_inicial": item.stock_inicial,
                            "ingresos": item.ingresos,
                            "egresos": item.egresos,
                            "stock_final": item.stock_final,
                        }
                        for item in conciliacion.items
                    ],
                },
                "auditoria": auditoria_original,
            })
            try:
                preconciliation_audit.merge_audit(
                    conciliacion.inventario_final_id,
                    auditoria,
                )
                calculo = calcular_preconciliacion(
                    conciliacion.inventario_final_id,
                    PreconciliacionCalculoEntrada(
                        inventarios_iniciales=[conciliacion.inventario_inicial_id]
                    ),
                    db,
                )
                analysis_id = preconciliation_audit.import_analysis(
                    analysis_id=f"legacy-{conciliacion.id}",
                    final_id=conciliacion.inventario_final_id,
                    initial_ids=[conciliacion.inventario_inicial_id],
                    name=f"{conciliacion.nombre} · migrada de {conciliacion.codigo}",
                    calculation=calculo,
                    created_at=conciliacion.creada_en,
                    updated_at=datetime.now(),
                    origin="CONCILIACION_LEGACY",
                    legacy_id=conciliacion.id,
                )
                reporte["conciliaciones_migradas"].append({
                    "conciliacion_id": conciliacion.id,
                    "analisis_id": analysis_id,
                })
            except Exception as error:  # informa cada caso sin ocultar los exitosos
                reporte["errores"].append({
                    "conciliacion_id": conciliacion.id,
                    "error": str(error),
                })

    (respaldo / "conciliaciones_legacy.json").write_text(
        json.dumps(instantaneas, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def importar_sqlite_local(ruta: Path, reporte: dict) -> None:
    if not ruta.exists():
        return
    with sqlite3.connect(ruta) as db:
        tablas = {
            fila[0]
            for fila in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "auditoria" in tablas:
            for final_id, datos_json in db.execute("SELECT final_id, datos FROM auditoria"):
                try:
                    preconciliation_audit.merge_audit(
                        int(final_id),
                        json.loads(datos_json),
                    )
                    reporte["auditorias_locales"] += 1
                except Exception as error:
                    reporte["errores"].append({
                        "auditoria_final_id": final_id,
                        "error": str(error),
                    })
        if "analisis" in tablas:
            filas = db.execute(
                """
                SELECT id, final_id, iniciales, nombre, creado_en,
                       actualizado_en, calculo
                FROM analisis
                """
            ).fetchall()
            for fila in filas:
                try:
                    preconciliation_audit.import_analysis(
                        analysis_id=str(fila[0]),
                        final_id=int(fila[1]),
                        initial_ids=json.loads(fila[2]),
                        name=str(fila[3]),
                        calculation=json.loads(fila[6]),
                        created_at=fecha_mysql(fila[4]),
                        updated_at=fecha_mysql(fila[5]),
                        origin="ANALISIS_LOCAL_MIGRADO",
                    )
                    reporte["analisis_locales"] += 1
                except Exception as error:
                    reporte["errores"].append({
                        "analisis_local_id": fila[0],
                        "error": str(error),
                    })


def importar_notas_locales(ruta: Path, reporte: dict) -> None:
    if not ruta.exists():
        return
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        reporte["errores"].append({
            "notas_locales": str(ruta),
            "error": str(error),
        })
        return
    for final_id, notas in datos.items():
        for codigo, nota in notas.items():
            try:
                guardar_nota(
                    int(final_id),
                    codigo,
                    str(nota.get("causa") or ""),
                    str(nota.get("observacion") or ""),
                    str(nota.get("estado") or "PENDIENTE"),
                    nota.get("controles") or {},
                )
                reporte["notas_locales"] += 1
            except Exception as error:
                reporte["errores"].append({
                    "nota_final_id": final_id,
                    "codigo": codigo,
                    "error": str(error),
                })


def mover_a_respaldo(origen: Path, respaldo: Path) -> None:
    if not origen.exists():
        return
    destino = respaldo / origen.relative_to(ROOT)
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(origen), str(destino))


def main() -> int:
    inspector = inspect(engine)
    faltantes = sorted(TABLAS_REQUERIDAS - set(inspector.get_table_names()))
    if faltantes:
        print(
            "Faltan tablas MySQL: " + ", ".join(faltantes) + "\n"
            "Ejecutá primero sql/migracion_v130.sql y volvé a iniciar este migrador."
        )
        return 2

    errores_tipo = validar_ids_bigint()
    if errores_tipo:
        print(
            "El esquema MySQL no coincide con la migración v1.30:\n- "
            + "\n- ".join(errores_tipo)
        )
        return 2

    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    respaldo = ROOT / "data" / f"respaldo_migracion_v130_{marca}"
    respaldo.mkdir(parents=True, exist_ok=True)
    reporte = {
        "ejecutado_en": datetime.now().isoformat(timespec="seconds"),
        "conciliaciones_detectadas": 0,
        "conciliaciones_migradas": [],
        "analisis_locales": 0,
        "auditorias_locales": 0,
        "notas_locales": 0,
        "tablas_locales": {},
        "fuentes_ausentes": [],
        "wms_retirado": [],
        "errores": [],
    }

    try:
        importar_almacenes_locales(reporte)
    except Exception as error:
        reporte["errores"].append({
            "almacenes_locales": "migración detenida",
            "error": str(error),
        })

    # La conciliación histórica se convierte después de copiar su auditoría
    # local, para que verificaciones, correcciones, manuales y scrap formen
    # parte del nuevo análisis.
    if not reporte["errores"]:
        importar_conciliaciones_legacy(respaldo, reporte)
        importar_sqlite_local(
            ROOT / "data" / "preconciliacion_auditoria.sqlite3",
            reporte,
        )
        importar_notas_locales(
            ROOT / "data" / "preconciliacion_notas.json",
            reporte,
        )

    analisis_mysql = preconciliation_audit.list_analyses()
    reporte["verificacion"] = {
        "analisis_mysql_totales": len(analisis_mysql),
        "conciliaciones_legacy_vinculadas": sum(
            1 for item in analisis_mysql
            if item.get("conciliacion_legacy_id") is not None
        ),
    }

    # Los archivos se retiran únicamente cuando toda la importación terminó
    # sin errores. Si algo falla quedan intactos para poder corregir y repetir.
    if not reporte["errores"]:
        for nombre in ARCHIVOS_LOCALES:
            mover_a_respaldo(ROOT / "data" / nombre, respaldo)
        for nombre in ARCHIVOS_WMS:
            ruta = ROOT / nombre
            if ruta.exists():
                reporte["wms_retirado"].append(nombre)
                mover_a_respaldo(ruta, respaldo)
        cache = ROOT / "app" / "__pycache__"
        for ruta in cache.glob("warehouse_store*.pyc") if cache.exists() else []:
            reporte["wms_retirado"].append(str(ruta.relative_to(ROOT)))
            mover_a_respaldo(ruta, respaldo)

    reporte_path = ROOT / "data" / "migracion_v130_resultado.json"
    reporte_path.write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Conciliaciones migradas: {len(reporte['conciliaciones_migradas'])}")
    print(
        "Conciliaciones legacy vinculadas en MySQL: "
        f"{reporte['verificacion']['conciliaciones_legacy_vinculadas']}"
    )
    print(f"Análisis locales migrados: {reporte['analisis_locales']}")
    print(f"Auditorías locales migradas: {reporte['auditorias_locales']}")
    print(f"Notas locales migradas: {reporte['notas_locales']}")
    print(
        "Registros de almacenes auxiliares migrados: "
        f"{sum(reporte['tablas_locales'].values())}"
    )
    print(f"Componentes WMS retirados: {len(reporte['wms_retirado'])}")
    print(f"Errores: {len(reporte['errores'])}")
    print(f"Respaldo: {respaldo}")
    print(f"Informe: {reporte_path}")
    return 1 if reporte["errores"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
