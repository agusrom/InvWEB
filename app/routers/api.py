import calendar
import hmac
import re
import unicodedata
from datetime import date, datetime, timedelta

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app import preconciliation_audit
from app.schemas import (
    PreconciliacionControlEntrada,
    PreconciliacionManualEntrada,
    PreconciliacionRemitoEntrada,
    PreconciliacionScrapEntrada,
)
from app.services.movements import _materiales_por_pieza, _componentes_terminales
from app.services.system_adjustments import obtener_ajustes_sistema, resumen_ajustes
from app.services.preconciliation_excel import crear_excel_preconciliacion
from app.services.preconciliation_indicators import calcular_indicadores_preconciliacion
from app.database import get_db
from app.local_count_store import (
    eliminar_caja,
    eliminar_cajas,
    eliminar_inventario as eliminar_conteo_local_inventario,
    eliminar_items as eliminar_conteo_local_items,
    listar_cajas,
    obtener_revision,
    registrar_caja,
    sincronizar_bases,
)
from app.local_reconciliation_store import (
    actualizar_controles_egreso,
    actualizar_controles_ingreso,
    agregar_egreso_manual,
    agregar_ingreso_manual,
    eliminar_egreso_manual,
    eliminar_auditoria,
    eliminar_ingreso_manual,
    excluir_item,
    guardar_auditoria,
    guardar_scrap,
    listar_codigos_excluidos,
    obtener_auditoria,
)
from app.local_recount_store import (
    crear_relacion,
    eliminar_relaciones_inventario,
)
from app.local_closing_store import (
    eliminar_mes_inventario,
    eliminar_mes_programacion,
    existe_cierre_programacion,
    guardar_mes_inventario,
    guardar_mes_programacion,
    vincular_inventario_programacion,
)
from app.models import (
    CausaDiferencia,
    Conciliacion,
    ConciliacionItem,
    Inventario,
    InventarioItem,
    Persona,
    Plantilla,
    PlantillaItem,
    ProgramacionInventario,
    Sector,
    TipoInventario,
)
from app.schemas import (
    AgregarArticuloInventarioEntrada,
    AgregarLoteMaterialEntrada,
    ArticuloInventarioEntrada,
    CausaDiferenciaEntrada,
    ConciliacionEntrada,
    ConciliacionEgresoManualEntrada,
    ConciliacionIngresoManualEntrada,
    ConciliacionMovimientosEntrada,
    PreconciliacionCalculoEntrada,
    PreconciliacionExportacionEntrada,
    PreconciliacionGuardarEntrada,
    PreconciliacionNotaEntrada,
    ConfiguracionIndicadoresEntrada,
    ConteoCajasEntrada,
    ConteoMedioMovilEntrada,
    ConteoEntrada,
    EliminarCajasMovilEntrada,
    EliminarFilasInventarioEntrada,
    FormatoVersionEntrada,
    InventarioDatosEntrada,
    InventarioEntrada,
    ReconteoCrearEntrada,
    ReabrirInventarioEntrada,
    PlantillaEntrada,
    PersonaEntrada,
    ProgramacionEntrada,
    SectorEntrada,
    TipoInventarioEntrada,
)
from app.serializers import (
    conciliacion_dict,
    inventario_dict,
    metricas_conteo_item,
    plantilla_dict,
    programacion_dict,
)
from app.services.excel import generar_excel
from app.services.piece_provider import (
    buscar_codigos_cliente_piezas,
    buscar_material,
    buscar_pieza,
    buscar_sugerencias_materiales,
    buscar_sugerencias_piezas,
    fuente_stock_actual,
    normalizar_codigo,
    obtener_estructura_recursiva,
)
from app.services.reports import generar_reporte
from app.services.movements import calcular_movimientos
from app.services.indicator_settings import (
    cargar_configuracion,
    guardar_configuracion,
)
from app.services.print_formats import (
    crear_version,
    formato_dict,
    listar_formatos,
    obtener_formato,
    version_actual_id,
    version_dict,
)
from app.services.stock_excel import (
    leer_reporte_stock,
    proveedores_texto,
)
from app.services.catalogs import (
    codigo_catalogo,
    persona_dict,
    sector_dict,
    tipo_dict,
)
from app.preconciliation_store import guardar_nota, notas_inventario


router = APIRouter(prefix="/api", tags=["Inventarios"])


def causa_diferencia_dict(
    causa: CausaDiferencia,
    usos: int = 0,
) -> dict:
    return {
        "codigo": causa.codigo,
        "nombre": causa.nombre,
        "descripcion": causa.descripcion,
        "categoria": causa.categoria,
        "orden": causa.orden,
        "activa": causa.activa,
        "usos": usos,
    }


def codigo_causa_desde_nombre(nombre: str) -> str:
    texto = unicodedata.normalize("NFKD", nombre)
    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )
    codigo = re.sub(r"[^A-Z0-9]+", "_", texto.upper()).strip("_")
    return codigo[:50] or "CAUSA"


def buscar_inventario(db: Session, inventario_id: int) -> Inventario:
    inventario = db.scalar(
        select(Inventario)
        .where(Inventario.id == inventario_id)
        .options(
            selectinload(Inventario.items),
        )
    )
    if inventario is None:
        raise HTTPException(status_code=404, detail="Inventario no encontrado")
    return inventario


def buscar_plantilla(db: Session, plantilla_id: int) -> Plantilla:
    plantilla = db.scalar(
        select(Plantilla)
        .where(Plantilla.id == plantilla_id)
        .options(selectinload(Plantilla.items))
    )
    if plantilla is None:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return plantilla


def buscar_programacion(
    db: Session,
    programacion_id: int,
) -> ProgramacionInventario:
    programacion = db.scalar(
        select(ProgramacionInventario)
        .where(ProgramacionInventario.id == programacion_id)
        .options(
            selectinload(ProgramacionInventario.plantilla),
            selectinload(ProgramacionInventario.inventarios),
        )
    )
    if programacion is None:
        raise HTTPException(
            status_code=404,
            detail="Programación no encontrada",
        )
    return programacion


def buscar_conciliacion(
    db: Session,
    conciliacion_id: int,
) -> Conciliacion:
    conciliacion = db.scalar(
        select(Conciliacion)
        .where(Conciliacion.id == conciliacion_id)
        .options(selectinload(Conciliacion.items))
    )
    if conciliacion is None:
        raise HTTPException(
            status_code=404,
            detail="Conciliación no encontrada",
        )
    return conciliacion


def sumar_un_mes(fecha_base: date, dia_mes: int) -> date:
    if fecha_base.month == 12:
        anio, mes = fecha_base.year + 1, 1
    else:
        anio, mes = fecha_base.year, fecha_base.month + 1
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, min(dia_mes, ultimo_dia))


def primer_dia_mes(fecha_base: date) -> date:
    return date(fecha_base.year, fecha_base.month, 1)


def sumar_mes_cierre(mes_cierre: date) -> date:
    return sumar_un_mes(primer_dia_mes(mes_cierre), 1)


def avanzar_programacion(
    programacion: ProgramacionInventario,
    hoy: date,
) -> None:
    fecha_ejecutada = programacion.fecha_proxima
    programacion.ultima_ejecucion = fecha_ejecutada
    if programacion.frecuencia == "UNA_VEZ":
        programacion.activa = False
        return

    cierre = programacion.mes_cierre_proximo or primer_dia_mes(
        fecha_ejecutada
    )

    if programacion.frecuencia == "SEMANAL":
        proxima = fecha_ejecutada + timedelta(days=7)
        cierre = primer_dia_mes(proxima)
    else:
        proxima = sumar_un_mes(fecha_ejecutada, programacion.dia_mes)
        cierre = sumar_mes_cierre(cierre)
    while proxima <= hoy:
        if programacion.frecuencia == "SEMANAL":
            proxima += timedelta(days=7)
            cierre = primer_dia_mes(proxima)
        else:
            proxima = sumar_un_mes(proxima, programacion.dia_mes)
            cierre = sumar_mes_cierre(cierre)
    programacion.fecha_proxima = proxima
    programacion.mes_cierre_proximo = cierre


def validar_items_plantilla(entrada: PlantillaEntrada):
    if entrada.categoria == "CICLICO" and len(entrada.items) != 1:
        raise HTTPException(
            status_code=422,
            detail="Una plantilla cíclica debe tener una sola pieza raíz",
        )
    if not entrada.items:
        raise HTTPException(
            status_code=422,
            detail="La plantilla debe tener al menos una pieza",
        )

    codigos_vistos: set[str] = set()
    items_validados = []
    for item in entrada.items:
        codigo = normalizar_codigo(item.codigo)
        if codigo in codigos_vistos:
            raise HTTPException(
                status_code=422,
                detail=f"El código {codigo} está repetido en la plantilla",
            )
        codigos_vistos.add(codigo)
        articulo = (
            buscar_material(codigo)
            if entrada.categoria == "MATERIA_PRIMA"
            else buscar_pieza(codigo)
        )
        if articulo is None:
            tabla = (
                "mtprim01"
                if entrada.categoria == "MATERIA_PRIMA"
                else "produc01"
            )
            raise HTTPException(
                status_code=422,
                detail=f"El código {codigo} no existe en {tabla}",
            )
        items_validados.append((item, articulo))
    return items_validados


def construir_items_plantilla(
    categoria: str,
    items_validados,
) -> list[PlantillaItem]:
    if categoria == "MATERIA_PRIMA":
        return [
            PlantillaItem(
                codigo=material.codigo,
                codigo_material=material.codigo,
                descripcion=material.descripcion,
                ubicacion=item.ubicacion.strip(),
                diametro=material.diametro,
                largo=material.largo,
                espesor=material.espesor,
                unidad=material.unidad,
                stock_referencia=material.stock_total,
                contar_material=True,
            )
            for item, material in items_validados
        ]

    return [
        PlantillaItem(
            codigo=pieza.codigo,
            codigo_cliente=pieza.codigo_cliente,
            codigo_material=pieza.codigo_material,
            descripcion=pieza.descripcion,
            ubicacion=item.ubicacion.strip(),
            stock_referencia=pieza.stock_terminado,
            tipo_estructura=pieza.tipo_estructura,
            contar_material=(
                item.contar_material
                and bool(pieza.codigo_material.strip())
            ),
        )
        for item, pieza in items_validados
    ]


def agregar_material_ciclico(
    destino: list[InventarioItem],
    material,
    *,
    codigo_padre: str,
    nivel: int,
    uso: float,
    ruta: str,
    ubicacion: str = "",
) -> None:
    lotes = material.lotes or [None]
    for lote in lotes:
        destino.append(
            InventarioItem(
                codigo=material.codigo,
                codigo_material=material.codigo,
                descripcion=material.descripcion,
                ubicacion=ubicacion,
                diametro=material.diametro,
                largo=material.largo,
                espesor=material.espesor,
                unidad=material.unidad,
                lote=lote.lote if lote else "",
                codigo_padre=codigo_padre,
                nivel=nivel,
                uso=uso,
                ruta=ruta,
                etapa="MATERIAL",
                operacion=lote.lote if lote else "",
                titulo_operacion=(
                    titulo_lote_material(lote.lote, material.descripcion)
                    if lote and lote.lote
                    else titulo_lote_material("", material.descripcion)
                ),
                stock_sistema=lote.stock if lote else 0,
            )
        )


def titulo_lote_material(lote: str, descripcion: str = "") -> str:
    base = f"Lote {lote}" if lote else "Sin lote"
    descripcion = str(descripcion or "").strip()
    return f"{base} · {descripcion}" if descripcion else base


def construir_filas_material_pieza(
    pieza,
    comunes: dict,
) -> list[InventarioItem]:
    descripcion_material = (
        str(getattr(pieza, "descripcion_material", "") or "").strip()
        or pieza.codigo_material
    )
    unidad_material = str(
        getattr(pieza, "unidad_material", "") or ""
    ).strip()
    base = dict(comunes)
    if unidad_material:
        base["unidad"] = unidad_material
    return [
        InventarioItem(
            **base,
            lote=lote.lote if lote else "",
            etapa="MATERIAL",
            operacion=lote.lote if lote else "",
            titulo_operacion=titulo_lote_material(
                lote.lote if lote else "",
                descripcion_material,
            ),
            stock_sistema=lote.stock if lote else 0,
            stock_pendiente=False,
        )
        for lote in (pieza.lotes_material or [None])
    ]


def agregar_pieza_ciclica(
    destino: list[InventarioItem],
    pieza,
    *,
    tipo_conteo: str,
    codigo_padre: str,
    nivel: int,
    uso: float,
    ruta: str,
    ubicacion: str = "",
) -> None:
    comunes = {
        "codigo": pieza.codigo,
        "codigo_cliente": pieza.codigo_cliente,
        "codigo_material": pieza.codigo_material,
        "descripcion": pieza.descripcion,
        "ubicacion": ubicacion,
        "codigo_padre": codigo_padre,
        "nivel": nivel,
        "uso": uso,
        "ruta": ruta,
        "tipo_estructura": (
            "PADRE"
            if nivel == 0
            else (
                "HIJO"
                if pieza.tipo_estructura == "INDEPENDIENTE"
                else pieza.tipo_estructura
            )
        ),
    }
    if pieza.tiene_operaciones_maestro:
        if tipo_conteo == "POR_OPERACION":
            destino.extend(
                InventarioItem(
                    **comunes,
                    etapa="OPERACION",
                    operacion=operacion.operacion,
                    titulo_operacion=operacion.titulo,
                    proveedor=operacion.proveedores,
                    stock_sistema=operacion.stock,
                )
                for operacion in pieza.operaciones
            )
        else:
            destino.append(
                InventarioItem(
                    **comunes,
                    etapa="PROCESO_GLOBAL",
                    operacion="TOTAL",
                    titulo_operacion="Total en proceso",
                    proveedor=pieza.proveedores_proceso,
                    stock_sistema=pieza.stock_proceso_total,
                )
            )
    destino.append(
        InventarioItem(
            **comunes,
            etapa="TERMINADO",
            titulo_operacion="Pieza terminada",
            stock_sistema=pieza.stock_terminado,
        )
    )


def construir_items_articulo(
    entrada: ArticuloInventarioEntrada,
    *,
    tipo_conteo: str,
    modalidad_conteo: str,
) -> tuple[object, list[InventarioItem]]:
    codigo = normalizar_codigo(entrada.codigo)
    if entrada.tipo_articulo == "MATERIA_PRIMA":
        material = buscar_material(codigo)
        if material is None:
            raise HTTPException(
                status_code=422,
                detail=f"El código {codigo} no existe en mtprim01",
            )
        items = [
            InventarioItem(
                codigo=material.codigo,
                codigo_material=material.codigo,
                descripcion=material.descripcion,
                diametro=material.diametro,
                largo=material.largo,
                espesor=material.espesor,
                unidad=material.unidad,
                lote=lote.lote if lote else "",
                etapa="MATERIAL",
                operacion=lote.lote if lote else "",
                titulo_operacion=(
                    titulo_lote_material(lote.lote, material.descripcion)
                    if lote and lote.lote
                    else titulo_lote_material("", material.descripcion)
                ),
                stock_sistema=lote.stock if lote else 0,
            )
            for lote in (material.lotes or [None])
        ]
        return material, items

    pieza = buscar_pieza(codigo)
    if pieza is None:
        raise HTTPException(
            status_code=422,
            detail=f"El código {codigo} no existe en produc01",
        )
    comunes = {
        "codigo": pieza.codigo,
        "codigo_cliente": pieza.codigo_cliente,
        "codigo_material": pieza.codigo_material,
        "descripcion": pieza.descripcion,
        "contar_material": entrada.contar_material,
        "tipo_estructura": pieza.tipo_estructura,
    }
    items: list[InventarioItem] = []
    if entrada.contar_material and pieza.codigo_material.strip():
        items.extend(construir_filas_material_pieza(pieza, comunes))
    if pieza.tiene_operaciones_maestro:
        if tipo_conteo == "POR_OPERACION":
            items.extend(
                InventarioItem(
                    **comunes,
                    etapa="OPERACION",
                    operacion=operacion.operacion,
                    titulo_operacion=operacion.titulo,
                    proveedor=operacion.proveedores,
                    stock_sistema=operacion.stock,
                )
                for operacion in pieza.operaciones
            )
        else:
            items.append(
                InventarioItem(
                    **comunes,
                    etapa="PROCESO_GLOBAL",
                    operacion="TOTAL",
                    titulo_operacion="Total en proceso",
                    proveedor=pieza.proveedores_proceso,
                    stock_sistema=pieza.stock_proceso_total,
                )
            )
    items.append(
        InventarioItem(
            **comunes,
            etapa="TERMINADO",
            titulo_operacion="Pieza terminada",
            stock_sistema=pieza.stock_terminado,
        )
    )
    if modalidad_conteo == "MEDIOS":
        items = [item for item in items if item.etapa == "TERMINADO"]
    return pieza, items


@router.get("/inicio")
def obtener_inicio(db: Session = Depends(get_db)):
    plantillas = db.scalars(
        select(Plantilla)
        .options(selectinload(Plantilla.items))
        .order_by(Plantilla.cliente)
    ).all()
    inventarios = db.scalars(
        select(Inventario)
        .options(selectinload(Inventario.items))
        .order_by(Inventario.fecha.desc(), Inventario.id.desc())
    ).all()
    programaciones = db.scalars(
        select(ProgramacionInventario)
        .options(
            selectinload(ProgramacionInventario.plantilla),
            selectinload(ProgramacionInventario.inventarios),
        )
        .order_by(
            ProgramacionInventario.activa.desc(),
            ProgramacionInventario.fecha_proxima,
        )
    ).all()
    conciliaciones = db.scalars(
        select(Conciliacion)
        .options(selectinload(Conciliacion.items))
        .order_by(Conciliacion.id.desc())
    ).all()
    return {
        "plantillas": [plantilla_dict(item) for item in plantillas],
        "inventarios": [inventario_dict(item) for item in inventarios],
        "causas_diferencia": [
            causa_diferencia_dict(causa)
            for causa in db.scalars(
                select(CausaDiferencia)
                .where(CausaDiferencia.activa.is_(True))
                .order_by(CausaDiferencia.orden, CausaDiferencia.nombre)
            ).all()
        ],
        "configuracion_indicadores": cargar_configuracion(db),
        "programaciones": [
            programacion_dict(item)
            for item in programaciones
        ],
        "conciliaciones": [
            conciliacion_dict(item)
            for item in conciliaciones
        ],
        "tipos_inventario": [
            tipo_dict(item)
            for item in db.scalars(
                select(TipoInventario)
                .where(TipoInventario.activo.is_(True))
                .order_by(TipoInventario.orden, TipoInventario.nombre)
            ).all()
        ],
        "personas": [
            persona_dict(item)
            for item in db.scalars(
                select(Persona)
                .where(Persona.activo.is_(True))
                .options(selectinload(Persona.sector))
                .order_by(Persona.orden, Persona.nombre)
            ).all()
        ],
    }


@router.get("/inicio-movil")
def obtener_inicio_movil(db: Session = Depends(get_db)):
    """Datos mínimos del portal móvil; evita cargar reportes y conciliaciones."""
    plantillas = db.scalars(
        select(Plantilla)
        .options(selectinload(Plantilla.items))
        .where(Plantilla.activa.is_(True))
        .order_by(Plantilla.cliente)
    ).all()
    inventarios = db.scalars(
        select(Inventario)
        .options(selectinload(Inventario.items))
        .order_by(Inventario.fecha.desc(), Inventario.id.desc())
    ).all()
    personas = db.scalars(
        select(Persona)
        .where(Persona.activo.is_(True))
        .options(selectinload(Persona.sector))
        .order_by(Persona.orden, Persona.nombre)
    ).all()
    return {
        "plantillas": [plantilla_dict(item) for item in plantillas],
        "inventarios": [inventario_dict(item) for item in inventarios],
        "personas": [persona_dict(item) for item in personas],
    }


@router.get("/reportes/resumen")
def obtener_reporte_resumen(
    dias: int = Query(default=90, ge=0, le=3650),
    mes_cierre: str = Query(
        default="",
        pattern=r"^(|\d{4}-(0[1-9]|1[0-2]))$",
    ),
    cliente: str = Query(default="", max_length=120),
    programacion: str = Query(
        default="todos",
        pattern="^(todos|programado|no_programado)$",
    ),
    tipo_inventario: str = Query(
        default="todos",
        pattern="^(todos|piezas|medios|materia_prima)$",
    ),
    agrupacion: str = Query(
        default="semanal",
        pattern="^(diaria|semanal|mensual)$",
    ),
    db: Session = Depends(get_db),
):
    inventarios = db.scalars(
        select(Inventario)
        .where(Inventario.estado == "Cerrado")
        .options(
            selectinload(Inventario.items),
            selectinload(Inventario.programacion),
        )
        .order_by(Inventario.fecha, Inventario.id)
    ).all()
    causas = db.scalars(select(CausaDiferencia)).all()
    programaciones = db.scalars(
        select(ProgramacionInventario)
        .options(selectinload(ProgramacionInventario.plantilla))
    ).all()
    return generar_reporte(
        list(inventarios),
        list(causas),
        list(programaciones),
        dias=dias,
        mes_cierre=mes_cierre,
        cliente=cliente.strip(),
        programacion=programacion,
        tipo_inventario=tipo_inventario,
        agrupacion=agrupacion,
        configuracion=cargar_configuracion(db),
    )


@router.get("/reportes/piezas")
def buscar_piezas_en_reportes(
    q: str = Query(min_length=2, max_length=100),
    limite: int = Query(default=12, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Sugiere códigos que realmente fueron incluidos en inventarios cerrados."""
    termino = q.strip().upper()
    filas = db.execute(
        select(
            InventarioItem.codigo,
            InventarioItem.descripcion,
            InventarioItem.codigo_cliente,
        )
        .join(Inventario, Inventario.id == InventarioItem.inventario_id)
        .where(
            Inventario.estado == "Cerrado",
            (
                func.upper(InventarioItem.codigo).contains(termino)
                | func.upper(InventarioItem.descripcion).contains(termino)
                | func.upper(InventarioItem.codigo_cliente).contains(termino)
            ),
        )
        .order_by(InventarioItem.codigo, InventarioItem.descripcion)
        .limit(limite * 6)
    ).all()
    resultados = []
    vistos = set()
    for codigo, descripcion, codigo_cliente in filas:
        clave = str(codigo or "").strip().upper()
        if not clave or clave in vistos:
            continue
        vistos.add(clave)
        resultados.append({
            "codigo": str(codigo or "").strip(),
            "descripcion": str(descripcion or "").strip(),
            "codigo_cliente": str(codigo_cliente or "").strip(),
        })
        if len(resultados) >= limite:
            break
    return {"resultados": resultados}


@router.get("/reportes/historial-pieza")
def obtener_historial_pieza(
    codigo: str = Query(min_length=1, max_length=80),
    db: Session = Depends(get_db),
):
    """Devuelve cada resultado histórico de un código en inventarios cerrados."""
    codigo_normalizado = codigo.strip().upper()
    filas = db.execute(
        select(Inventario, InventarioItem)
        .join(InventarioItem, InventarioItem.inventario_id == Inventario.id)
        .where(
            Inventario.estado == "Cerrado",
            func.upper(func.trim(InventarioItem.codigo)) == codigo_normalizado,
        )
        .order_by(Inventario.fecha.desc(), Inventario.id.desc(), InventarioItem.id)
    ).all()
    causas = {
        causa.codigo: causa.nombre
        for causa in db.scalars(select(CausaDiferencia)).all()
    }
    resultados = []
    for inventario, item in filas:
        metrica = metricas_conteo_item(item)
        resultados.append({
            "inventario_id": inventario.id,
            "inventario_codigo": inventario.codigo,
            "fecha": inventario.fecha.isoformat(),
            "cerrado_en": (
                inventario.cerrado_en.isoformat(timespec="seconds")
                if inventario.cerrado_en else None
            ),
            "cliente": inventario.cliente,
            "codigo": item.codigo,
            "codigo_cliente": item.codigo_cliente,
            "descripcion": item.descripcion,
            "etapa": item.etapa,
            "operacion": item.operacion,
            "titulo_operacion": item.titulo_operacion,
            "lote": item.lote,
            "unidad": item.unidad,
            "stock_pendiente": item.stock_pendiente,
            "stock_sistema": item.stock_sistema,
            "conteo_fisico": item.conteo_fisico,
            "diferencia": metrica["diferencia"],
            "desvio_porcentaje": metrica["desvio_porcentaje"],
            "dentro_tolerancia": metrica["dentro_tolerancia"],
            "causa": causas.get(item.causa_diferencia_codigo, ""),
            "ajustado_sistema": item.ajustado_sistema,
            "observaciones": item.observaciones,
        })
    cabecera = resultados[0] if resultados else None
    return {
        "codigo": codigo.strip(),
        "descripcion": cabecera["descripcion"] if cabecera else "",
        "codigo_cliente": cabecera["codigo_cliente"] if cabecera else "",
        "cantidad_resultados": len(resultados),
        "resultados": resultados,
    }


@router.get("/configuracion/indicadores")
def obtener_configuracion_indicadores(
    db: Session = Depends(get_db),
):
    return cargar_configuracion(db)


@router.put("/configuracion/indicadores")
def modificar_configuracion_indicadores(
    entrada: ConfiguracionIndicadoresEntrada,
    db: Session = Depends(get_db),
):
    if entrada.alerta_cliente_pct > entrada.objetivo_confiabilidad_pct:
        raise HTTPException(
            status_code=422,
            detail=(
                "El umbral de alerta no puede ser mayor que el objetivo "
                "de confiabilidad."
            ),
        )
    return guardar_configuracion(db, entrada.model_dump())


@router.get("/catalogos")
def obtener_catalogos(db: Session = Depends(get_db)):
    return {
        "tipos_inventario": [
            tipo_dict(item)
            for item in db.scalars(
                select(TipoInventario).order_by(
                    TipoInventario.orden,
                    TipoInventario.nombre,
                )
            ).all()
        ],
        "sectores": [
            sector_dict(item)
            for item in db.scalars(
                select(Sector)
                .options(selectinload(Sector.personas))
                .order_by(Sector.orden, Sector.nombre)
            ).all()
        ],
        "personas": [
            persona_dict(item)
            for item in db.scalars(
                select(Persona)
                .options(selectinload(Persona.sector))
                .order_by(Persona.orden, Persona.nombre)
            ).all()
        ],
    }


def validar_tipo_inventario(
    db: Session,
    entrada: TipoInventarioEntrada,
    codigo_actual: str | None = None,
) -> None:
    if entrada.modalidad == "MEDIOS" and entrada.motor != "PIEZAS":
        raise HTTPException(
            status_code=422,
            detail="La modalidad de medios requiere el motor de piezas.",
        )
    if (
        entrada.modalidad == "MEDIOS"
        and entrada.formato_impresion != "MEDIOS"
    ) or (
        entrada.modalidad != "MEDIOS"
        and entrada.formato_impresion == "MEDIOS"
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "La modalidad de vacíos, llenos y rotos debe usar "
                "el formato Medios."
            ),
        )
    if entrada.motor == "MATERIA_PRIMA" and entrada.formato_impresion not in {
        "MATERIA_PRIMA",
        "LISTADO_SIMPLE",
    }:
        raise HTTPException(
            status_code=422,
            detail="Elegí un formato compatible con materia prima.",
        )
    if entrada.motor == "CICLICO" and entrada.formato_impresion not in {
        "CICLICO",
        "RESUMEN_VERTICAL",
        "DETALLE_ETAPAS",
        "LISTADO_SIMPLE",
    }:
        raise HTTPException(
            status_code=422,
            detail="Elegí un formato compatible con inventario cíclico.",
        )
    if entrada.motor == "PIEZAS" and entrada.formato_impresion in {
        "MATERIA_PRIMA",
        "CICLICO",
    }:
        raise HTTPException(
            status_code=422,
            detail="Elegí un formato compatible con piezas.",
        )
    duplicado = db.scalar(
        select(TipoInventario).where(
            func.lower(TipoInventario.nombre)
            == entrada.nombre.strip().lower(),
            TipoInventario.codigo != (codigo_actual or ""),
        )
    )
    if duplicado:
        raise HTTPException(
            status_code=409,
            detail="Ya existe un tipo de inventario con ese nombre.",
        )


@router.post("/tipos-inventario", status_code=201)
def crear_tipo_inventario(
    entrada: TipoInventarioEntrada,
    db: Session = Depends(get_db),
):
    validar_tipo_inventario(db, entrada)
    base = codigo_catalogo(entrada.nombre) or "TIPO"
    codigo = base
    numero = 2
    while db.get(TipoInventario, codigo):
        sufijo = f"_{numero}"
        codigo = f"{base[:50 - len(sufijo)]}{sufijo}"
        numero += 1
    tipo = TipoInventario(codigo=codigo, **entrada.model_dump())
    tipo.nombre = tipo.nombre.strip()
    tipo.descripcion = tipo.descripcion.strip()
    db.add(tipo)
    db.commit()
    return tipo_dict(tipo)


@router.put("/tipos-inventario/{codigo}")
def modificar_tipo_inventario(
    codigo: str,
    entrada: TipoInventarioEntrada,
    db: Session = Depends(get_db),
):
    tipo = db.get(TipoInventario, codigo.strip().upper())
    if tipo is None:
        raise HTTPException(status_code=404, detail="Tipo no encontrado")
    validar_tipo_inventario(db, entrada, tipo.codigo)
    for clave, valor in entrada.model_dump().items():
        setattr(tipo, clave, valor.strip() if isinstance(valor, str) else valor)
    db.commit()
    return tipo_dict(tipo)


@router.post("/sectores", status_code=201)
def crear_sector(
    entrada: SectorEntrada,
    db: Session = Depends(get_db),
):
    if db.scalar(
        select(Sector).where(
            func.lower(Sector.nombre) == entrada.nombre.strip().lower()
        )
    ):
        raise HTTPException(status_code=409, detail="El sector ya existe.")
    sector = Sector(**entrada.model_dump())
    sector.nombre = sector.nombre.strip()
    sector.descripcion = sector.descripcion.strip()
    db.add(sector)
    db.commit()
    db.refresh(sector)
    return sector_dict(sector)


@router.put("/sectores/{sector_id}")
def modificar_sector(
    sector_id: int,
    entrada: SectorEntrada,
    db: Session = Depends(get_db),
):
    sector = db.get(Sector, sector_id)
    if sector is None:
        raise HTTPException(status_code=404, detail="Sector no encontrado")
    duplicado = db.scalar(
        select(Sector).where(
            func.lower(Sector.nombre) == entrada.nombre.strip().lower(),
            Sector.id != sector.id,
        )
    )
    if duplicado:
        raise HTTPException(status_code=409, detail="El sector ya existe.")
    for clave, valor in entrada.model_dump().items():
        setattr(
            sector,
            clave,
            valor.strip() if isinstance(valor, str) else valor,
        )
    db.commit()
    db.refresh(sector)
    return sector_dict(sector)


def validar_sector_persona(db: Session, sector_id: int | None) -> None:
    if sector_id is not None and db.get(Sector, sector_id) is None:
        raise HTTPException(status_code=422, detail="El sector no existe.")


@router.post("/personas", status_code=201)
def crear_persona(
    entrada: PersonaEntrada,
    db: Session = Depends(get_db),
):
    validar_sector_persona(db, entrada.sector_id)
    persona = Persona(**entrada.model_dump())
    persona.nombre = persona.nombre.strip()
    persona.legajo = persona.legajo.strip()
    persona.contacto = persona.contacto.strip()
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona_dict(persona)


@router.put("/personas/{persona_id}")
def modificar_persona(
    persona_id: int,
    entrada: PersonaEntrada,
    db: Session = Depends(get_db),
):
    persona = db.get(Persona, persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    validar_sector_persona(db, entrada.sector_id)
    for clave, valor in entrada.model_dump().items():
        setattr(
            persona,
            clave,
            valor.strip() if isinstance(valor, str) else valor,
        )
    db.commit()
    db.refresh(persona)
    return persona_dict(persona)


@router.get("/formatos-impresion")
def obtener_formatos_impresion(db: Session = Depends(get_db)):
    return {
        "formatos": [
            formato_dict(formato)
            for formato in listar_formatos(db)
        ]
    }


@router.get("/formatos-impresion/{codigo}")
def obtener_formato_impresion(
    codigo: str,
    db: Session = Depends(get_db),
):
    formato = obtener_formato(db, codigo.strip().upper())
    if formato is None:
        raise HTTPException(
            status_code=404,
            detail="Diseño de impresión no encontrado",
        )
    return formato_dict(formato, detalle=True)


@router.put("/formatos-impresion/{codigo}")
def guardar_formato_impresion(
    codigo: str,
    entrada: FormatoVersionEntrada,
    db: Session = Depends(get_db),
):
    formato = obtener_formato(db, codigo.strip().upper())
    if formato is None:
        raise HTTPException(
            status_code=404,
            detail="Diseño de impresión no encontrado",
        )
    if not formato.editable:
        raise HTTPException(
            status_code=409,
            detail="Este diseño no admite personalización",
        )

    claves_esperadas = {
        columna.clave
        for columna in formato.versiones[-1].columnas
    }
    claves_recibidas = [columna.clave for columna in entrada.columnas]
    if len(claves_recibidas) != len(set(claves_recibidas)):
        raise HTTPException(
            status_code=422,
            detail="Hay columnas repetidas en el diseño",
        )
    if set(claves_recibidas) != claves_esperadas:
        raise HTTPException(
            status_code=422,
            detail="Las columnas no corresponden al formato seleccionado",
        )
    visibles = [columna for columna in entrada.columnas if columna.visible]
    if len(visibles) < 2:
        raise HTTPException(
            status_code=422,
            detail="El diseño debe conservar al menos dos columnas visibles",
        )
    if any(not columna.titulo.strip() for columna in entrada.columnas):
        raise HTTPException(
            status_code=422,
            detail="Todas las columnas deben conservar un título",
        )
    if not entrada.nombre.strip():
        raise HTTPException(
            status_code=422,
            detail="Ingresá un nombre para identificar esta versión",
        )

    version = crear_version(db, formato, entrada.model_dump())
    return {
        "mensaje": (
            f'Diseño "{version.nombre}" guardado como versión '
            f"{version.numero}"
        ),
        "configuracion": version_dict(version),
    }


@router.get("/causas-diferencia")
def listar_causas_diferencia(db: Session = Depends(get_db)):
    usos = dict(
        db.execute(
            select(
                InventarioItem.causa_diferencia_codigo,
                func.count(InventarioItem.id),
            )
            .where(InventarioItem.causa_diferencia_codigo.is_not(None))
            .group_by(InventarioItem.causa_diferencia_codigo)
        ).all()
    )
    causas = db.scalars(
        select(CausaDiferencia).order_by(
            CausaDiferencia.orden,
            CausaDiferencia.nombre,
        )
    ).all()
    return {
        "causas": [
            causa_diferencia_dict(causa, usos.get(causa.codigo, 0))
            for causa in causas
        ]
    }


@router.post("/causas-diferencia", status_code=201)
def crear_causa_diferencia(
    entrada: CausaDiferenciaEntrada,
    db: Session = Depends(get_db),
):
    nombre = entrada.nombre.strip()
    if not nombre:
        raise HTTPException(
            status_code=422,
            detail="Ingresá un nombre para la causa",
        )
    codigo_base = codigo_causa_desde_nombre(nombre)
    codigo = codigo_base
    sufijo = 2
    while db.get(CausaDiferencia, codigo) is not None:
        agregado = f"_{sufijo}"
        codigo = f"{codigo_base[:50 - len(agregado)]}{agregado}"
        sufijo += 1
    causa = CausaDiferencia(
        codigo=codigo,
        nombre=nombre,
        descripcion=entrada.descripcion.strip(),
        categoria=entrada.categoria,
        orden=entrada.orden,
        activa=entrada.activa,
    )
    db.add(causa)
    db.commit()
    return causa_diferencia_dict(causa)


@router.put("/causas-diferencia/{codigo}")
def modificar_causa_diferencia(
    codigo: str,
    entrada: CausaDiferenciaEntrada,
    db: Session = Depends(get_db),
):
    causa = db.get(CausaDiferencia, codigo)
    if causa is None:
        raise HTTPException(status_code=404, detail="Causa no encontrada")
    nombre = entrada.nombre.strip()
    if not nombre:
        raise HTTPException(
            status_code=422,
            detail="Ingresá un nombre para la causa",
        )
    causa.nombre = nombre
    causa.descripcion = entrada.descripcion.strip()
    causa.categoria = entrada.categoria
    causa.orden = entrada.orden
    causa.activa = entrada.activa
    db.commit()
    usos = db.scalar(
        select(func.count(InventarioItem.id)).where(
            InventarioItem.causa_diferencia_codigo == causa.codigo
        )
    ) or 0
    return causa_diferencia_dict(causa, usos)


@router.delete("/causas-diferencia/{codigo}", status_code=204)
def eliminar_causa_diferencia(
    codigo: str,
    db: Session = Depends(get_db),
):
    causa = db.get(CausaDiferencia, codigo)
    if causa is None:
        raise HTTPException(status_code=404, detail="Causa no encontrada")
    usos = db.scalar(
        select(func.count(InventarioItem.id)).where(
            InventarioItem.causa_diferencia_codigo == causa.codigo
        )
    ) or 0
    if usos:
        raise HTTPException(
            status_code=409,
            detail=(
                "La causa ya fue utilizada. Desactivala para conservar "
                "el historial."
            ),
        )
    db.delete(causa)
    db.commit()
    return Response(status_code=204)


def numero_traza(valor: float) -> str:
    return f"{valor:.4f}".rstrip("0").rstrip(".")


def codigos_presentes_inventarios(
    inventario_inicial: Inventario,
    inventario_final: Inventario,
) -> set[str]:
    """Códigos que fueron incluidos como renglón en al menos un inventario."""
    codigos_iniciales = {
        normalizar_codigo(item.codigo) for item in inventario_inicial.items
    }
    codigos_finales = {
        normalizar_codigo(item.codigo) for item in inventario_final.items
    }
    return (codigos_iniciales | codigos_finales) - {""}


def explotar_conteo_inventario(
    inventario: Inventario,
    codigos_padre: set[str] | None = None,
    codigos_resultado: set[str] | None = None,
) -> dict[str, dict]:
    padres_permitidos = (
        {normalizar_codigo(codigo) for codigo in codigos_padre}
        if codigos_padre is not None
        else None
    )
    resultados_permitidos = (
        {normalizar_codigo(codigo) for codigo in codigos_resultado}
        if codigos_resultado is not None
        else None
    )
    sin_contar = [
        item.codigo
        for item in inventario.items
        if (
            padres_permitidos is None
            or normalizar_codigo(item.codigo) in padres_permitidos
        )
        if item.conteo_fisico is None
    ]
    if sin_contar:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{inventario.codigo} todavía tiene renglones sin contar. "
                "Completalo antes de usarlo en una conciliación."
            ),
        )
    explotado: dict[str, dict] = {}
    estructuras: dict[str, list] = {}
    descripciones: dict[str, str] = {}
    for item in inventario.items:
        codigo_padre = normalizar_codigo(item.codigo)
        if (
            padres_permitidos is not None
            and codigo_padre not in padres_permitidos
        ):
            continue
        cantidad_padre = float(item.conteo_fisico or 0)
        if item.etapa == "MATERIAL":
            cantidad_padre = equivalente_material_en_piezas(
                codigo_padre, cantidad_padre
            )[0]
        if codigo_padre not in estructuras:
            try:
                nodos = obtener_estructura_recursiva(codigo_padre)
            except RuntimeError as error:
                raise HTTPException(
                    status_code=409,
                    detail=str(error),
                ) from error
            codigos_con_hijos = {
                nodo.codigo_padre
                for nodo in nodos
                if nodo.codigo_padre
            }
            estructuras[codigo_padre] = [
                nodo
                for nodo in nodos
                if nodo.codigo not in codigos_con_hijos
            ]

        for componente in estructuras[codigo_padre]:
            codigo_componente = normalizar_codigo(componente.codigo)
            if (
                resultados_permitidos is not None
                and codigo_componente not in resultados_permitidos
            ):
                continue
            equivalente = cantidad_padre * componente.uso_acumulado
            if codigo_componente not in descripciones:
                if codigo_componente == codigo_padre:
                    descripcion = item.descripcion
                else:
                    articulo = (
                        buscar_pieza(codigo_componente)
                        or buscar_material(codigo_componente)
                    )
                    descripcion = (
                        articulo.descripcion
                        if articulo is not None
                        else "Componente de estructura"
                    )
                descripciones[codigo_componente] = descripcion
            fila = explotado.setdefault(
                codigo_componente,
                {
                    "descripcion": descripciones[codigo_componente],
                    "cantidad": 0.0,
                    "trazas": {},
                },
            )
            fila["cantidad"] += equivalente
            traza = fila["trazas"].setdefault(
                codigo_padre,
                {
                    "cantidad_padre": 0.0,
                    "uso": componente.uso_acumulado,
                    "equivalente": 0.0,
                },
            )
            traza["cantidad_padre"] += cantidad_padre
            traza["equivalente"] += equivalente

    for fila in explotado.values():
        fila["detalle"] = "; ".join(
            (
                f"{codigo}: {numero_traza(datos['cantidad_padre'])} "
                f"× {numero_traza(datos['uso'])} "
                f"= {numero_traza(datos['equivalente'])}"
            )
            for codigo, datos in sorted(fila["trazas"].items())
        )
        del fila["trazas"]
    return explotado


def descripcion_codigo_movimiento(codigo: str) -> str:
    articulo = buscar_pieza(codigo) or buscar_material(codigo)
    return (
        articulo.descripcion
        if articulo is not None
        else "Código presente en movimientos"
    )


def aplicar_movimientos_conciliacion(
    conciliacion: Conciliacion,
    movimientos: dict,
    stock_inicial: dict[str, dict] | None = None,
    stock_final: dict[str, dict] | None = None,
) -> None:
    items_por_codigo = {item.codigo: item for item in conciliacion.items}
    for codigo, item in items_por_codigo.items():
        ingresos = float(movimientos["ingresos_por_codigo"].get(codigo, 0))
        egresos = float(movimientos["egresos_por_codigo"].get(codigo, 0))
        item.ingresos = ingresos
        item.egresos = egresos


def codigos_completos_inventario(inventario: Inventario) -> set[str]:
    grupos: dict[str, list[InventarioItem]] = {}
    for item in inventario.items:
        grupos.setdefault(normalizar_codigo(item.codigo), []).append(item)
    return {
        codigo for codigo, items in grupos.items()
        if codigo and items and all(item.conteo_fisico is not None for item in items)
    }


def stock_sistema_por_codigo(inventario: Inventario) -> dict[str, float]:
    resultado: dict[str, float] = {}
    for item in inventario.items:
        codigo = normalizar_codigo(item.codigo)
        if not codigo:
            continue
        cantidad = float(item.stock_sistema or 0)
        if item.etapa == "MATERIAL":
            cantidad = equivalente_material_en_piezas(codigo, cantidad)[0]
        resultado[codigo] = resultado.get(codigo, 0.0) + cantidad
    return resultado


def datos_consumo_material(codigo: str) -> tuple[float, str]:
    """Devuelve el consumo unitario de produc01 y una unidad auditable."""
    pieza = buscar_pieza(codigo)
    consumo = float(getattr(pieza, "consumo_material", 1) or 1) if pieza else 1.0
    if consumo <= 0:
        consumo = 1.0
    unidad = str(getattr(pieza, "unidad_consumo", "") or "C/U") if pieza else "C/U"
    return consumo, unidad


def equivalente_material_en_piezas(codigo: str, cantidad: float) -> tuple[float, float, str]:
    """Convierte stock o conteo de MP a piezas: cantidad de MP / CONS_."""
    consumo, unidad = datos_consumo_material(codigo)
    return float(cantidad or 0) / consumo, consumo, unidad


def detalle_stock_sistema_por_codigo(inventario: Inventario) -> dict[str, dict]:
    """Desglosa el stock capturado y convierte la MP a piezas equivalentes."""
    resultado: dict[str, dict] = {}
    for item in inventario.items:
        codigo = normalizar_codigo(item.codigo)
        if not codigo:
            continue
        detalle = resultado.setdefault(codigo, {
            "materia_prima": 0.0,
            "en_proceso": 0.0,
            "producto_terminado": 0.0,
            "stock_asignado": 0.0,
            "materia_prima_equivalente": 0.0,
            "consumo_material": 1.0,
            "unidad_consumo": "C/U",
        })
        cantidad = float(item.stock_sistema or 0)
        if item.etapa == "MATERIAL":
            detalle["materia_prima"] += cantidad
            equivalente, consumo, unidad = equivalente_material_en_piezas(codigo, cantidad)
            detalle["materia_prima_equivalente"] += equivalente
            detalle["consumo_material"] = consumo
            detalle["unidad_consumo"] = unidad
        elif item.etapa in {"OPERACION", "PROCESO_GLOBAL"}:
            detalle["en_proceso"] += cantidad
        elif item.etapa == "TERMINADO":
            detalle["producto_terminado"] += cantidad
            detalle["stock_asignado"] += float(item.stock_asignado or 0)
    for detalle in resultado.values():
        detalle["total_general"] = (
            detalle["materia_prima_equivalente"]
            + detalle["en_proceso"]
            + detalle["producto_terminado"]
        )
        # Alias de compatibilidad para análisis guardados/exportadores previos.
        detalle["total_productivo"] = detalle["total_general"]
    return resultado


def detalle_conteo_fisico_por_codigo(inventario: Inventario) -> dict[str, dict]:
    """Desglosa el físico y expresa la MP en piezas equivalentes."""
    resultado: dict[str, dict] = {}
    for item in inventario.items:
        codigo = normalizar_codigo(item.codigo)
        if not codigo or item.conteo_fisico is None:
            continue
        detalle = resultado.setdefault(codigo, {
            "materia_prima": 0.0, "materia_prima_equivalente": 0.0,
            "en_proceso": 0.0, "producto_terminado": 0.0,
            "consumo_material": 1.0, "unidad_consumo": "C/U",
        })
        cantidad = float(item.conteo_fisico or 0)
        if item.etapa == "MATERIAL":
            detalle["materia_prima"] += cantidad
            equivalente, consumo, unidad = equivalente_material_en_piezas(codigo, cantidad)
            detalle["materia_prima_equivalente"] += equivalente
            detalle["consumo_material"] = consumo
            detalle["unidad_consumo"] = unidad
        elif item.etapa in {"OPERACION", "PROCESO_GLOBAL"}:
            detalle["en_proceso"] += cantidad
        elif item.etapa == "TERMINADO":
            detalle["producto_terminado"] += cantidad
    for detalle in resultado.values():
        detalle["total_general"] = (
            detalle["materia_prima_equivalente"]
            + detalle["en_proceso"]
            + detalle["producto_terminado"]
        )
        detalle["total_productivo"] = detalle["total_general"]
    return resultado


def grupos_material_compartido(inventario: Inventario) -> dict[str, list[str]]:
    """Agrupa las piezas del inventario que declaran el mismo código de MP."""
    piezas_por_material: dict[str, set[str]] = {}
    for item in inventario.items:
        codigo = normalizar_codigo(item.codigo)
        material = normalizar_codigo(item.codigo_material)
        if not codigo or not material:
            continue
        piezas_por_material.setdefault(material, set()).add(codigo)
    return {
        material: sorted(codigos)
        for material, codigos in piezas_por_material.items()
        if len(codigos) > 1
    }


def conteo_explotado_grupos_material_compartido(
    inventario: Inventario,
    grupos: dict[str, list[str]],
) -> dict[str, float]:
    """Suma cada MP+lote una vez y agrega Proceso/PT de cada pieza del grupo."""
    resultado: dict[str, float] = {}
    for material, codigos in grupos.items():
        miembros = set(codigos)
        productivo = sum(
            float(item.conteo_fisico or 0)
            for item in inventario.items
            if normalizar_codigo(item.codigo) in miembros
            and item.etapa != "MATERIAL"
            and item.conteo_fisico is not None
        )
        filas_por_lote: dict[str, list[InventarioItem]] = {}
        for item in inventario.items:
            if (
                item.etapa != "MATERIAL"
                or normalizar_codigo(item.codigo) not in miembros
                or normalizar_codigo(item.codigo_material or item.codigo) != material
                or item.conteo_fisico is None
            ):
                continue
            clave_lote = str(item.lote or "").strip().upper()
            filas_por_lote.setdefault(clave_lote, []).append(item)
        material_equivalente = 0.0
        for filas in filas_por_lote.values():
            cantidad = max(float(item.conteo_fisico or 0) for item in filas)
            propietario = max(
                filas,
                key=lambda item: (
                    abs(float(item.stock_sistema or 0)),
                    abs(float(item.conteo_fisico or 0)),
                    -(item.id or 0),
                ),
            )
            material_equivalente += equivalente_material_en_piezas(
                normalizar_codigo(propietario.codigo),
                cantidad,
            )[0]
        resultado[material] = productivo + material_equivalente
    return resultado


def _sumar_detalle_grupo(filas: list[dict], campo: str) -> dict:
    detalles = [fila.get(campo, {}) or {} for fila in filas]
    resultado = {
        clave: sum(float(detalle.get(clave, 0) or 0) for detalle in detalles)
        for clave in (
            "materia_prima",
            "materia_prima_equivalente",
            "en_proceso",
            "producto_terminado",
            "stock_asignado",
        )
    }
    consumos = {
        float(detalle.get("consumo_material", 1) or 1)
        for detalle in detalles
    }
    unidades = {
        str(detalle.get("unidad_consumo", "") or "").strip()
        for detalle in detalles
        if str(detalle.get("unidad_consumo", "") or "").strip()
    }
    resultado["consumo_material"] = next(iter(consumos)) if len(consumos) == 1 else None
    resultado["unidad_consumo"] = next(iter(unidades)) if len(unidades) == 1 else "VARIAS"
    resultado["total_general"] = (
        resultado["materia_prima_equivalente"]
        + resultado["en_proceso"]
        + resultado["producto_terminado"]
    )
    resultado["total_productivo"] = resultado["total_general"]
    return resultado


def agrupar_filas_material_compartido(
    filas: list[dict],
    grupos: dict[str, list[str]],
    tolerancia: float,
    iniciales_grupo: dict[str, float] | None = None,
    actuales_grupo: dict[str, float] | None = None,
) -> list[dict]:
    """Consolida piezas con MP compartida sin duplicar el ingreso de esa MP."""
    por_codigo = {
        normalizar_codigo(fila.get("codigo")): fila
        for fila in filas
        if normalizar_codigo(fila.get("codigo"))
    }
    consumidos: set[str] = set()
    resultado: list[dict] = []
    for material, codigos in sorted(grupos.items()):
        miembros = [por_codigo[codigo] for codigo in codigos if codigo in por_codigo]
        if not miembros:
            continue
        consumidos.update(codigo for codigo in codigos if codigo in por_codigo)
        ingresos_unicos: dict[str, dict] = {}
        for fila in miembros:
            for detalle in fila.get("detalle_ingresos", []):
                clave = preconciliation_audit.source_key("IN", detalle)
                ingresos_unicos.setdefault(clave, detalle)
        detalles_ingreso = list(ingresos_unicos.values())
        detalles_egreso = [
            detalle
            for fila in miembros
            for detalle in fila.get("detalle_egresos", [])
        ]
        fisico_inicial = float((iniciales_grupo or {}).get(
            material,
            sum(float(fila.get("fisico_inicial", 0) or 0) for fila in miembros),
        ))
        ingresos = sum(float(item.get("cantidad", 0) or 0) for item in detalles_ingreso)
        egresos = sum(float(fila.get("egresos", 0) or 0) for fila in miembros)
        conteo_explotado = float((actuales_grupo or {}).get(
            material,
            sum(
                float(fila.get("conteo_explotado_actual", fila.get("fisico_actual", 0)) or 0)
                for fila in miembros
            ),
        ))
        detalle_sistema = _sumar_detalle_grupo(miembros, "detalle_sistema")
        detalle_fisico = _sumar_detalle_grupo(miembros, "detalle_fisico")
        sistema_actual = float(detalle_sistema["total_general"])
        conteo_actual = float(detalle_fisico["total_general"])
        esperado = fisico_inicial + ingresos - egresos
        ajustes = [
            ajuste
            for fila in miembros
            for ajuste in fila.get("ajustes_sistema", [])
        ]
        detalle_piezas = [{
            "codigo": fila.get("codigo", ""),
            "descripcion": fila.get("descripcion", ""),
            "sistema_actual": float(fila.get("sistema_actual", 0) or 0),
            "conteo_actual": float(fila.get("conteo_actual", 0) or 0),
            "diferencia_sistema": float(fila.get("diferencia_sistema", 0) or 0),
            "porcentaje_desvio_sistema": fila.get("porcentaje_desvio_sistema"),
            "sistema_ok": bool(fila.get("sistema_ok")),
            "detalle_sistema": fila.get("detalle_sistema", {}),
            "detalle_fisico": fila.get("detalle_fisico", {}),
            "ajustes_sistema": fila.get("ajustes_sistema", []),
            "resumen_ajustes_sistema": fila.get("resumen_ajustes_sistema", {}),
        } for fila in miembros]
        codigo_grupo = f"MP:{material}"
        resultado.append({
            "codigo": codigo_grupo,
            "codigo_material": material,
            "codigos": codigos,
            "es_grupo_mp": True,
            "descripcion": f"MP {material} compartida por {' + '.join(codigos)}",
            "fisico_inicial": fisico_inicial,
            "ingresos": ingresos,
            "egresos": egresos,
            "detalle_ingresos": detalles_ingreso,
            "detalle_egresos": detalles_egreso,
            "esperado": esperado,
            "sistema_actual": sistema_actual,
            "ajustes_sistema": ajustes,
            "resumen_ajustes_sistema": resumen_ajustes(ajustes),
            "detalle_sistema": detalle_sistema,
            "detalle_fisico": detalle_fisico,
            "detalle_piezas": detalle_piezas,
            "conteo_actual": conteo_actual,
            "conteo_explotado_actual": conteo_explotado,
            "fisico_actual": conteo_explotado,
            "diferencia_sistema": conteo_actual - sistema_actual,
            "diferencia_conciliacion": conteo_explotado - esperado,
            "porcentaje_desvio_sistema": porcentaje_desvio(conteo_actual, sistema_actual),
            "porcentaje_desvio_conciliacion": porcentaje_desvio(conteo_explotado, esperado),
            "sistema_ok": all(pieza["sistema_ok"] for pieza in detalle_piezas),
            "conciliacion_ok": dentro_tolerancia_comparacion(conteo_explotado, esperado, tolerancia),
        })
    resultado.extend(
        fila for codigo, fila in por_codigo.items()
        if codigo not in consumidos
    )
    return sorted(resultado, key=lambda fila: str(fila.get("codigo", "")))


def conteo_directo_por_codigo(inventario: Inventario) -> dict[str, float]:
    """Conteo tal como fue registrado, en la misma granularidad del sistema.

    La materia prima se convierte a piezas equivalentes mediante CONS_.
    """
    resultado: dict[str, float] = {}
    for item in inventario.items:
        codigo = normalizar_codigo(item.codigo)
        if not codigo or item.conteo_fisico is None:
            continue
        cantidad = float(item.conteo_fisico)
        if item.etapa == "MATERIAL":
            cantidad = equivalente_material_en_piezas(codigo, cantidad)[0]
        resultado[codigo] = resultado.get(codigo, 0.0) + cantidad
    return resultado


def dentro_tolerancia_comparacion(fisico: float, referencia: float, tolerancia: float) -> bool:
    if referencia == 0:
        return fisico == 0
    return abs((fisico - referencia) * 100 / referencia) <= tolerancia + 1e-9


def porcentaje_desvio(valor: float, referencia: float) -> float | None:
    if referencia == 0:
        return 0.0 if valor == 0 else None
    return (valor - referencia) * 100 / referencia


@router.get("/preconciliacion/inventarios-disponibles")
def inventarios_disponibles_preconciliacion(db: Session = Depends(get_db)):
    inventarios = db.scalars(
        select(Inventario)
        .options(selectinload(Inventario.items))
        .order_by(Inventario.fecha.desc(), Inventario.id.desc())
    ).all()
    return [
        {
            "id": inventario.id,
            "codigo": inventario.codigo,
            "cliente": inventario.cliente,
            "fecha": inventario.fecha.isoformat(),
            "estado": inventario.estado,
            "contados": len(codigos_completos_inventario(inventario)),
        }
        for inventario in inventarios
        if inventario.items and codigos_completos_inventario(inventario)
    ]


@router.get("/inventarios/{inventario_id}/preconciliacion")
def opciones_preconciliacion(
    inventario_id: int,
    db: Session = Depends(get_db),
):
    final = buscar_inventario(db, inventario_id)
    candidatos = db.scalars(
        select(Inventario)
        .options(selectinload(Inventario.items))
        .where(
            Inventario.id != final.id,
            Inventario.fecha < final.fecha,
            Inventario.cliente == final.cliente,
            Inventario.categoria == final.categoria,
            Inventario.modalidad_conteo == final.modalidad_conteo,
        )
        .order_by(Inventario.fecha.desc(), Inventario.id.desc())
    ).all()
    elegibles = [
        inventario for inventario in candidatos
        if inventario.items
        and all(item.conteo_fisico is not None for item in inventario.items)
    ]
    causas = db.scalars(
        select(CausaDiferencia)
        .where(CausaDiferencia.activa.is_(True))
        .order_by(CausaDiferencia.orden, CausaDiferencia.nombre)
    ).all()
    completos = codigos_completos_inventario(final)
    historial_sistema = []
    for historico in elegibles[:3]:
        conteos_historicos = conteo_directo_por_codigo(historico)
        sistema_historico = stock_sistema_por_codigo(historico)
        historial_sistema.append({
            "id": historico.id,
            "codigo": historico.codigo,
            "fecha": historico.fecha.isoformat(),
            "filas": {
                codigo: {
                    "conteo": conteos_historicos.get(codigo),
                    "sistema": sistema_historico.get(codigo, 0),
                    "diferencia": conteos_historicos[codigo] - sistema_historico.get(codigo, 0),
                }
                for codigo in conteos_historicos
            },
        })
    return {
        "final": {
            "id": final.id,
            "codigo": final.codigo,
            "cliente": final.cliente,
            "fecha": final.fecha.isoformat(),
            "estado": final.estado,
            "contados": len(completos),
            "total": len({normalizar_codigo(item.codigo) for item in final.items}),
        },
        "iniciales": [
            {
                "id": item.id,
                "codigo": item.codigo,
                "fecha": item.fecha.isoformat(),
                "estado": item.estado,
            }
            for item in elegibles
        ],
        "causas": [causa_diferencia_dict(causa) for causa in causas],
        "notas": notas_inventario(final.id),
        "historial_sistema": historial_sistema,
        "tolerancia": cargar_configuracion(db)["tolerancia_pct"],
    }


def completar_codigos_cliente_preconciliacion(calculation: dict) -> dict:
    """Agrega CCOD_ a piezas, orígenes de egreso y auditoría de remitos."""
    codes = set()
    for scenario in calculation.get("escenarios", []):
        for row in scenario.get("filas", []):
            if row.get("es_grupo_mp"):
                codes.update(row.get("codigos", []))
            else:
                codes.add(row.get("codigo", ""))
            for detail in row.get("detalle_ingresos", []):
                codes.add(detail.get("codigo_material", detail.get("codigo", "")))
            for detail in row.get("detalle_egresos", []):
                codes.add(detail.get("pieza_origen", ""))
    for movement in calculation.get("movimientos", []):
        codes.add(movement.get("codigo", ""))
    customer_codes = buscar_codigos_cliente_piezas(codes)
    for scenario in calculation.get("escenarios", []):
        for row in scenario.get("filas", []):
            if row.get("es_grupo_mp"):
                row["codigos_cliente"] = {
                    codigo: customer_codes.get(normalizar_codigo(codigo), "")
                    for codigo in row.get("codigos", [])
                }
                row["codigo_cliente"] = " + ".join(
                    valor for valor in row["codigos_cliente"].values() if valor
                )
                for pieza in row.get("detalle_piezas", []):
                    pieza["codigo_cliente"] = customer_codes.get(
                        normalizar_codigo(pieza.get("codigo")),
                        "",
                    )
            else:
                row["codigo_cliente"] = customer_codes.get(normalizar_codigo(row.get("codigo")), "")
            for detail in row.get("detalle_ingresos", []):
                source_code = detail.get("codigo_material", detail.get("codigo", ""))
                detail["codigo_cliente_origen"] = customer_codes.get(
                    normalizar_codigo(source_code),
                    "",
                )
            for detail in row.get("detalle_egresos", []):
                detail["codigo_cliente_origen"] = customer_codes.get(
                    normalizar_codigo(detail.get("pieza_origen")),
                    "",
                )
    for movement in calculation.get("movimientos", []):
        movement["codigo_cliente"] = customer_codes.get(
            normalizar_codigo(movement.get("codigo")),
            "",
        )
    return calculation


@router.post("/inventarios/{inventario_id}/preconciliacion/calcular")
def calcular_preconciliacion(
    inventario_id: int,
    entrada: PreconciliacionCalculoEntrada,
    db: Session = Depends(get_db),
):
    final = buscar_inventario(db, inventario_id)
    if len(set(entrada.inventarios_iniciales)) != len(entrada.inventarios_iniciales):
        raise HTTPException(status_code=422, detail="No repitas inventarios iniciales")
    tolerancia = float(cargar_configuracion(db)["tolerancia_pct"])
    codigos_finales = codigos_completos_inventario(final)
    detalle_sistema = detalle_stock_sistema_por_codigo(final)
    detalle_fisico = detalle_conteo_fisico_por_codigo(final)
    grupos_compartidos = grupos_material_compartido(final)
    conteo_final_compartido = conteo_explotado_grupos_material_compartido(
        final,
        grupos_compartidos,
    )
    conteos_iniciales_compartidos: dict[int, dict[str, float]] = {}
    grupo_por_pieza = {
        codigo: f"MP:{material}"
        for material, codigos in grupos_compartidos.items()
        for codigo in codigos
    }
    escenarios = []
    for inicial_id in entrada.inventarios_iniciales:
        inicial = buscar_inventario(db, inicial_id)
        conteos_iniciales_compartidos[inicial.id] = (
            conteo_explotado_grupos_material_compartido(
                inicial,
                grupos_compartidos,
            )
        )
        if inicial.fecha >= final.fecha:
            raise HTTPException(status_code=422, detail="El inventario inicial debe ser anterior al final")
        if (
            inicial.cliente != final.cliente
            or inicial.categoria != final.categoria
            or inicial.modalidad_conteo != final.modalidad_conteo
        ):
            raise HTTPException(status_code=422, detail="Los inventarios seleccionados no son comparables")
        padres = codigos_finales & codigos_completos_inventario(inicial)
        if not padres:
            escenarios.append({
                "inicial": {"id": inicial.id, "codigo": inicial.codigo, "fecha": inicial.fecha.isoformat()},
                "filas": [],
                "advertencias": ["No hay códigos completos comunes con el inventario actual."],
                "error": "Sin códigos completos comunes",
            })
            continue
        try:
            stock_inicial = explotar_conteo_inventario(inicial, padres, padres)
            stock_final = explotar_conteo_inventario(final, padres, padres)
            codigos = sorted(set(stock_inicial) | set(stock_final))
            movimientos = calcular_movimientos(
                inicial.ultimo_remito_ingreso,
                final.ultimo_remito_ingreso,
                inicial.ultimo_remito_egreso,
                final.ultimo_remito_egreso,
                fecha_inicial=inicial.fecha,
                fecha_final=final.fecha,
                codigos_padre=padres,
                codigos_resultado=set(codigos),
            )
            ajustes_por_codigo = obtener_ajustes_sistema(
                set(codigos),
                inicial.fecha,
                final.fecha,
            )
            filas = []
            for codigo in codigos:
                fisico_inicial = float(stock_inicial.get(codigo, {}).get("cantidad", 0))
                conteo_explotado_actual = float(stock_final.get(codigo, {}).get("cantidad", 0))
                detalle_sistema_codigo = detalle_sistema.get(codigo, {
                    "materia_prima": 0,
                    "materia_prima_equivalente": 0,
                    "en_proceso": 0,
                    "producto_terminado": 0,
                    "stock_asignado": 0,
                    "consumo_material": 1,
                    "unidad_consumo": "C/U",
                    "total_general": 0,
                    "total_productivo": 0,
                })
                detalle_fisico_codigo = detalle_fisico.get(codigo, {
                    "materia_prima": 0,
                    "materia_prima_equivalente": 0,
                    "en_proceso": 0,
                    "producto_terminado": 0,
                    "consumo_material": 1,
                    "unidad_consumo": "C/U",
                    "total_general": 0,
                    "total_productivo": 0,
                })
                sistema_actual = float(detalle_sistema_codigo["total_general"])
                conteo_actual = float(detalle_fisico_codigo["total_general"])
                ingresos = float(movimientos["ingresos_por_codigo"].get(codigo, 0))
                egresos = float(movimientos["egresos_por_codigo"].get(codigo, 0))
                esperado = fisico_inicial + ingresos - egresos
                ajustes_sistema = ajustes_por_codigo.get(codigo, [])
                filas.append({
                    "codigo": codigo,
                    "descripcion": (
                        stock_final.get(codigo, {}).get("descripcion")
                        or stock_inicial.get(codigo, {}).get("descripcion")
                        or ""
                    ),
                    "fisico_inicial": fisico_inicial,
                    "ingresos": ingresos,
                    "egresos": egresos,
                    "detalle_ingresos": movimientos["detalles_ingreso"].get(codigo, []),
                    "detalle_egresos": movimientos["detalles_egreso"].get(codigo, []),
                    "esperado": esperado,
                    "sistema_actual": sistema_actual,
                    "ajustes_sistema": ajustes_sistema,
                    "resumen_ajustes_sistema": resumen_ajustes(ajustes_sistema),
                    "detalle_sistema": detalle_sistema_codigo,
                    "detalle_fisico": detalle_fisico_codigo,
                    "conteo_actual": conteo_actual,
                    "conteo_explotado_actual": conteo_explotado_actual,
                    # Alias temporal para clientes v0.82; siempre representa
                    # el valor explotado usado por la conciliación.
                    "fisico_actual": conteo_explotado_actual,
                    "diferencia_sistema": conteo_actual - sistema_actual,
                    "diferencia_conciliacion": conteo_explotado_actual - esperado,
                    "porcentaje_desvio_sistema": porcentaje_desvio(conteo_actual, sistema_actual),
                    "porcentaje_desvio_conciliacion": porcentaje_desvio(conteo_explotado_actual, esperado),
                    "sistema_ok": dentro_tolerancia_comparacion(conteo_actual, sistema_actual, tolerancia),
                    "conciliacion_ok": dentro_tolerancia_comparacion(conteo_explotado_actual, esperado, tolerancia),
                })
            escenarios.append({
                "inicial": {"id": inicial.id, "codigo": inicial.codigo, "fecha": inicial.fecha.isoformat()},
                "filas": filas,
                "advertencias": movimientos.get("advertencias", []),
            })
        except (HTTPException, ValueError, RuntimeError) as error:
            detalle = error.detail if isinstance(error, HTTPException) else str(error)
            escenarios.append({
                "inicial": {"id": inicial.id, "codigo": inicial.codigo, "fecha": inicial.fecha.isoformat()},
                "filas": [],
                "advertencias": [detalle],
                "error": detalle,
            })
    for escenario in escenarios:
        if escenario.get("filas"):
            escenario["filas"] = agrupar_filas_material_compartido(
                escenario["filas"],
                grupos_compartidos,
                tolerancia,
                conteos_iniciales_compartidos.get(
                    int(escenario["inicial"]["id"]),
                    {},
                ),
                conteo_final_compartido,
            )
    material_cache = {}
    structure_cache = {}

    def resolve_manual(movement, codes):
        code = movement["codigo"]
        codigos_reales = set()
        for codigo in codes:
            if codigo.startswith("MP:"):
                material = codigo.split(":", 1)[1]
                codigos_reales.update(grupos_compartidos.get(material, []))
            else:
                codigos_reales.add(codigo)
        if code in codigos_reales:
            return {grupo_por_pieza.get(code, code): 1.0}
        if movement["tipo"] == "IN":
            cache_key = tuple(sorted(codigos_reales))
            if cache_key not in material_cache:
                material_cache[cache_key] = _materiales_por_pieza(codigos_reales)
            return {
                grupo_por_pieza.get(piece, piece): 1.0
                for piece in material_cache[cache_key].get(code, set())
            }
        uses = {}
        for component in _componentes_terminales(code, structure_cache):
            if component["codigo"] in codigos_reales:
                destino = grupo_por_pieza.get(component["codigo"], component["codigo"])
                uses[destino] = uses.get(destino, 0) + component["uso"]
        return uses

    result = preconciliation_audit.reconcile(final.id, final.fecha, escenarios, tolerancia,
        dentro_tolerancia_comparacion, resolve_manual)
    completar_codigos_cliente_preconciliacion(result)
    result["notas_guardadas"] = notas_inventario(final.id)
    result["indicadores"] = calcular_indicadores_preconciliacion(
        result,
        result["notas_guardadas"],
    )
    return result


@router.post("/inventarios/{inventario_id}/preconciliacion/guardar")
def guardar_analisis_preconciliacion(
    inventario_id: int,
    entrada: PreconciliacionGuardarEntrada,
    db: Session = Depends(get_db),
):
    final = buscar_inventario(db, inventario_id)
    calculation = calcular_preconciliacion(
        inventario_id,
        PreconciliacionCalculoEntrada(inventarios_iniciales=entrada.inventarios_iniciales),
        db,
    )
    analysis_id = preconciliation_audit.save_analysis(
        final.id, final.codigo, calculation["escenarios"], calculation, entrada.nombre
    )
    return {"id": analysis_id, "nombre": entrada.nombre.strip(), "calculo": calculation}


@router.get("/preconciliacion/analisis-guardados")
def listar_analisis_guardados(db: Session = Depends(get_db)):
    analisis = preconciliation_audit.list_analyses(include_calculation=True)
    inventario_ids = {
        int(inventario_id)
        for item in analisis
        for inventario_id in [item["final_id"], *item["inventarios_iniciales"]]
    }
    inventarios = {
        inventario.id: inventario.codigo
        for inventario in db.scalars(
            select(Inventario).where(Inventario.id.in_(inventario_ids))
        ).all()
    } if inventario_ids else {}
    return [
        {
            **{key: value for key, value in item.items() if key != "calculo"},
            "final_codigo": inventarios.get(item["final_id"], ""),
            "iniciales_codigos": [
                inventarios.get(inventario_id, f"#{inventario_id}")
                for inventario_id in item["inventarios_iniciales"]
            ],
            "indicadores": calcular_indicadores_preconciliacion(
                item["calculo"],
                notas_inventario(item["final_id"]),
            ),
        }
        for item in analisis
    ]


@router.get("/preconciliacion/analisis-guardados/{analisis_id}")
def obtener_analisis_guardado(analisis_id: str, db: Session = Depends(get_db)):
    analysis = preconciliation_audit.get_analysis(analisis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")
    buscar_inventario(db, analysis["final_id"])
    return analysis


@router.delete("/preconciliacion/analisis-guardados/{analisis_id}", status_code=204)
def eliminar_analisis_guardado(analisis_id: str):
    if not preconciliation_audit.delete_analysis(analisis_id):
        raise HTTPException(status_code=404, detail="Análisis no encontrado")
    return Response(status_code=204)


@router.post("/inventarios/{inventario_id}/preconciliacion/exportar")
def exportar_preconciliacion(
    inventario_id: int,
    entrada: PreconciliacionExportacionEntrada,
    db: Session = Depends(get_db),
):
    final = buscar_inventario(db, inventario_id)
    saved = preconciliation_audit.get_analysis(entrada.analisis_id) if entrada.analisis_id else None
    if entrada.analisis_id and saved is None:
        raise HTTPException(status_code=404, detail="Análisis guardado no encontrado")
    if saved and saved["final_id"] != inventario_id:
        raise HTTPException(status_code=422, detail="El análisis no corresponde al inventario")
    calculation = saved["calculo"] if saved else calcular_preconciliacion(
        inventario_id,
        PreconciliacionCalculoEntrada(inventarios_iniciales=entrada.inventarios_iniciales),
        db,
    )
    if saved and entrada.vista == "CONCILIACION":
        selected_ids = set(entrada.inventarios_iniciales)
        calculation = dict(calculation, escenarios=[
            scenario for scenario in calculation["escenarios"]
            if scenario["inicial"]["id"] in selected_ids
        ])
        if not calculation["escenarios"]:
            raise HTTPException(status_code=422, detail="El escenario no pertenece al análisis guardado")
    completar_codigos_cliente_preconciliacion(calculation)
    setup = opciones_preconciliacion(inventario_id, db)
    stream = crear_excel_preconciliacion(
        final,
        calculation,
        calculation.get("notas_guardadas", setup["notas"]),
        setup["historial_sistema"],
        entrada.vista,
    )
    scope = "analisis" if entrada.vista == "ANALISIS" else "conciliacion"
    filename = f"{scope}_{final.codigo}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/inventarios/{inventario_id}/preconciliacion/movimientos/remito")
def guardar_remito_preconciliacion(
    inventario_id: int,
    entrada: PreconciliacionRemitoEntrada,
    db: Session = Depends(get_db),
):
    buscar_inventario(db, inventario_id)
    if len(set(entrada.inventarios_iniciales)) != len(entrada.inventarios_iniciales):
        raise HTTPException(status_code=422, detail="No repitas inventarios iniciales")
    try:
        saved = preconciliation_audit.edit_many(
            inventario_id,
            [item.model_dump() for item in entrada.movimientos],
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if not saved["requiere_recalculo"] and not entrada.recalcular:
        return {
            "recalculado": False,
            "movimientos": saved["movimientos"],
        }
    calculation = calcular_preconciliacion(
        inventario_id,
        PreconciliacionCalculoEntrada(
            inventarios_iniciales=entrada.inventarios_iniciales,
        ),
        db,
    )
    return {
        "recalculado": True,
        "calculo": calculation,
    }


@router.put("/inventarios/{inventario_id}/preconciliacion/movimientos/{clave}")
def editar_movimiento_preconciliacion(inventario_id: int, clave: str,
    entrada: PreconciliacionControlEntrada, db: Session = Depends(get_db)):
    buscar_inventario(db, inventario_id)
    try:
        return preconciliation_audit.edit(inventario_id, clave, entrada.model_dump(exclude_unset=True))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.post("/inventarios/{inventario_id}/preconciliacion/movimientos", status_code=201)
def agregar_movimiento_preconciliacion(inventario_id: int,
    entrada: PreconciliacionManualEntrada, db: Session = Depends(get_db)):
    final = buscar_inventario(db, inventario_id)
    if entrada.fecha > final.fecha:
        raise HTTPException(status_code=422, detail="La fecha no puede ser posterior al inventario final")
    payload = entrada.model_dump(mode="json")
    payload["codigo"] = normalizar_codigo(payload["codigo"])
    payload["remito"] = payload["remito"].strip()
    if not payload["codigo"] or not payload["remito"]:
        raise HTTPException(status_code=422, detail="Completá código y remito")
    return preconciliation_audit.add_manual(inventario_id, payload)


@router.delete("/inventarios/{inventario_id}/preconciliacion/movimientos/{clave}")
def eliminar_movimiento_preconciliacion(inventario_id: int, clave: str, db: Session = Depends(get_db)):
    buscar_inventario(db, inventario_id)
    try:
        return preconciliation_audit.edit(inventario_id, clave, delete=True)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.put("/inventarios/{inventario_id}/preconciliacion/scrap")
def scrap_preconciliacion(inventario_id: int, entrada: PreconciliacionScrapEntrada, db: Session = Depends(get_db)):
    final = buscar_inventario(db, inventario_id)
    inicial = buscar_inventario(db, entrada.inicial_id)
    if inicial.fecha >= final.fecha or (inicial.cliente, inicial.categoria, inicial.modalidad_conteo) != (final.cliente, final.categoria, final.modalidad_conteo):
        raise HTTPException(status_code=422, detail="Inventarios no comparables")
    return preconciliation_audit.set_scrap(inventario_id, entrada.inicial_id, entrada.codigo, entrada.cantidad)


@router.put("/inventarios/{inventario_id}/preconciliacion/nota")
def actualizar_nota_preconciliacion(
    inventario_id: int,
    entrada: PreconciliacionNotaEntrada,
    db: Session = Depends(get_db),
):
    buscar_inventario(db, inventario_id)
    if entrada.causa and db.get(CausaDiferencia, entrada.causa) is None:
        raise HTTPException(status_code=422, detail="La causa seleccionada no existe")
    return guardar_nota(
        inventario_id,
        entrada.codigo,
        entrada.causa,
        entrada.observacion,
        entrada.estado,
        entrada.controles,
    )


def sincronizar_movimientos_auditados(
    conciliacion: Conciliacion,
    db: Session,
) -> None:
    """Copia a los totales existentes el valor efectivo de la auditoría local."""
    auditoria = obtener_auditoria(conciliacion.id)
    for item in conciliacion.items:
        local = auditoria["items"].get(item.id)
        if local is not None:
            item.ingresos = float(local["ingresos_calculados"])
            item.egresos = float(local["egresos_calculados"])
    db.commit()


@router.post("/conciliaciones", status_code=201)
def crear_conciliacion(
    entrada: ConciliacionEntrada,
    db: Session = Depends(get_db),
):
    if entrada.inventario_inicial_id == entrada.inventario_final_id:
        raise HTTPException(
            status_code=422,
            detail="Elegí dos inventarios diferentes",
        )
    inicial = buscar_inventario(db, entrada.inventario_inicial_id)
    final = buscar_inventario(db, entrada.inventario_final_id)
    if final.fecha < inicial.fecha:
        raise HTTPException(
            status_code=422,
            detail="El inventario final no puede ser anterior al inicial",
        )
    codigos_padre = codigos_presentes_inventarios(inicial, final)
    if not codigos_padre:
        raise HTTPException(
            status_code=422,
            detail=(
                "Los inventarios seleccionados no tienen piezas contadas"
            ),
        )
    stock_inicial = explotar_conteo_inventario(
        inicial,
        codigos_padre,
        codigos_padre,
    )
    stock_final = explotar_conteo_inventario(
        final,
        codigos_padre,
        codigos_padre,
    )
    codigos = sorted(set(stock_inicial) | set(stock_final))
    if not codigos:
        raise HTTPException(
            status_code=422,
            detail="Los inventarios seleccionados no tienen artículos",
        )

    ultimo_id = db.scalar(select(func.max(Conciliacion.id))) or 0
    conciliacion = Conciliacion(
        codigo=f"CON-{final.fecha.year}-{ultimo_id + 1:03d}",
        nombre=entrada.nombre.strip(),
        inventario_inicial_id=inicial.id,
        inventario_final_id=final.id,
        inventario_inicial_codigo=inicial.codigo,
        inventario_final_codigo=final.codigo,
        fecha_inicial=inicial.fecha,
        fecha_final=final.fecha,
        remito_ingreso_inicial=inicial.ultimo_remito_ingreso,
        remito_ingreso_final=final.ultimo_remito_ingreso,
        remito_egreso_inicial=inicial.ultimo_remito_egreso,
        remito_egreso_final=final.ultimo_remito_egreso,
    )
    conciliacion.items = [
        ConciliacionItem(
            codigo=codigo,
            descripcion=(
                stock_final.get(codigo, {}).get("descripcion")
                or stock_inicial.get(codigo, {}).get("descripcion")
                or ""
            ),
            stock_inicial=stock_inicial.get(codigo, {}).get("cantidad", 0),
            detalle_inicial=stock_inicial.get(codigo, {}).get("detalle", ""),
            stock_final=stock_final.get(codigo, {}).get("cantidad", 0),
            detalle_final=stock_final.get(codigo, {}).get("detalle", ""),
        )
        for codigo in codigos
    ]
    try:
        movimientos = calcular_movimientos(
            conciliacion.remito_ingreso_inicial,
            conciliacion.remito_ingreso_final,
            conciliacion.remito_egreso_inicial,
            conciliacion.remito_egreso_final,
            fecha_inicial=inicial.fecha,
            fecha_final=final.fecha,
            codigos_padre=codigos_padre,
            codigos_resultado=set(codigos),
        )
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    aplicar_movimientos_conciliacion(
        conciliacion,
        movimientos,
        stock_inicial,
        stock_final,
    )
    db.add(conciliacion)
    db.commit()
    conciliacion = buscar_conciliacion(db, conciliacion.id)
    guardar_auditoria(conciliacion.id, movimientos, conciliacion.items)
    sincronizar_movimientos_auditados(conciliacion, db)
    return conciliacion_dict(
        buscar_conciliacion(db, conciliacion.id)
    )


@router.post("/conciliaciones/{conciliacion_id}/recalcular-movimientos")
def recalcular_movimientos_conciliacion(
    conciliacion_id: int,
    db: Session = Depends(get_db),
):
    conciliacion = buscar_conciliacion(db, conciliacion_id)
    inicial = buscar_inventario(db, conciliacion.inventario_inicial_id)
    final = buscar_inventario(db, conciliacion.inventario_final_id)
    codigos_padre = codigos_presentes_inventarios(inicial, final)
    if not codigos_padre:
        raise HTTPException(
            status_code=422,
            detail="Los inventarios seleccionados no tienen piezas contadas",
        )
    stock_inicial = explotar_conteo_inventario(
        inicial,
        codigos_padre,
        codigos_padre,
    )
    stock_final = explotar_conteo_inventario(
        final,
        codigos_padre,
        codigos_padre,
    )
    codigos_resultado = set(stock_inicial) | set(stock_final)
    codigos_excluidos = listar_codigos_excluidos(conciliacion.id)
    codigos_resultado = {
        codigo for codigo in codigos_resultado
        if normalizar_codigo(codigo) not in codigos_excluidos
    }
    if not codigos_resultado:
        raise HTTPException(
            status_code=422,
            detail=(
                "Los inventarios no tienen códigos contados disponibles para "
                "conciliar"
            ),
        )
    items_por_codigo = {
        normalizar_codigo(item.codigo): item for item in conciliacion.items
    }
    for item in list(conciliacion.items):
        if normalizar_codigo(item.codigo) not in codigos_resultado:
            conciliacion.items.remove(item)
    for codigo in sorted(codigos_resultado):
        item = items_por_codigo.get(codigo)
        if item is None:
            item = ConciliacionItem(codigo=codigo)
            conciliacion.items.append(item)
        item.descripcion = (
            stock_final.get(codigo, {}).get("descripcion")
            or stock_inicial.get(codigo, {}).get("descripcion")
            or ""
        )
        item.stock_inicial = stock_inicial.get(codigo, {}).get("cantidad", 0)
        item.detalle_inicial = stock_inicial.get(codigo, {}).get("detalle", "")
        item.stock_final = stock_final.get(codigo, {}).get("cantidad", 0)
        item.detalle_final = stock_final.get(codigo, {}).get("detalle", "")
    try:
        movimientos = calcular_movimientos(
            conciliacion.remito_ingreso_inicial,
            conciliacion.remito_ingreso_final,
            conciliacion.remito_egreso_inicial,
            conciliacion.remito_egreso_final,
            fecha_inicial=inicial.fecha,
            fecha_final=final.fecha,
            codigos_padre=codigos_padre,
            codigos_resultado=codigos_resultado,
        )
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    aplicar_movimientos_conciliacion(conciliacion, movimientos)
    db.commit()
    conciliacion = buscar_conciliacion(db, conciliacion.id)
    guardar_auditoria(conciliacion.id, movimientos, conciliacion.items)
    sincronizar_movimientos_auditados(conciliacion, db)
    return conciliacion_dict(
        buscar_conciliacion(db, conciliacion.id)
    )


@router.delete("/conciliaciones/{conciliacion_id}/items/{item_id}")
def eliminar_item_conciliacion(
    conciliacion_id: int,
    item_id: int,
    db: Session = Depends(get_db),
):
    conciliacion = buscar_conciliacion(db, conciliacion_id)
    item = next((fila for fila in conciliacion.items if fila.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Fila de conciliación no encontrada")
    if len(conciliacion.items) <= 1:
        raise HTTPException(status_code=409, detail="La conciliación debe conservar al menos una fila")
    excluir_item(conciliacion.id, item.id, item.codigo)
    db.delete(item)
    db.commit()
    return conciliacion_dict(buscar_conciliacion(db, conciliacion.id))


@router.put("/conciliaciones/{conciliacion_id}")
def guardar_movimientos_conciliacion(
    conciliacion_id: int,
    entrada: ConciliacionMovimientosEntrada,
    db: Session = Depends(get_db),
):
    conciliacion = buscar_conciliacion(db, conciliacion_id)
    items_por_id = {item.id: item for item in conciliacion.items}
    try:
        actualizar_controles_ingreso(
            conciliacion_id,
            [control.model_dump() for control in entrada.controles_ingreso],
        )
        actualizar_controles_egreso(
            conciliacion_id,
            [control.model_dump() for control in entrada.controles_egreso],
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    valores_scrap = {}
    for movimiento in entrada.items:
        item = items_por_id.get(movimiento.item_id)
        if item is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El ítem {movimiento.item_id} no pertenece "
                    "a la conciliación"
                ),
            )
        item.ingresos = movimiento.ingresos
        item.egresos = movimiento.egresos
        valores_scrap[item.id] = movimiento.scrap
    guardar_scrap(conciliacion_id, valores_scrap)
    db.commit()
    return conciliacion_dict(
        buscar_conciliacion(db, conciliacion.id)
    )


@router.post("/conciliaciones/{conciliacion_id}/ingresos-manuales")
def crear_ingreso_manual_conciliacion(
    conciliacion_id: int,
    entrada: ConciliacionIngresoManualEntrada,
    db: Session = Depends(get_db),
):
    conciliacion = buscar_conciliacion(db, conciliacion_id)
    item = next(
        (fila for fila in conciliacion.items if fila.id == entrada.item_id),
        None,
    )
    if item is None:
        raise HTTPException(
            status_code=400,
            detail="La pieza elegida no pertenece a esta conciliación",
        )
    agregar_ingreso_manual(
        conciliacion_id=conciliacion_id,
        item_id=item.id,
        codigo=item.codigo,
        codigo_material=entrada.codigo_material,
        remito=entrada.remito,
        fecha=entrada.fecha,
        cantidad=entrada.cantidad,
        observacion=entrada.observacion,
    )
    sincronizar_movimientos_auditados(conciliacion, db)
    return conciliacion_dict(buscar_conciliacion(db, conciliacion_id))


@router.delete(
    "/conciliaciones/{conciliacion_id}/ingresos-manuales/{movimiento_clave}"
)
def borrar_ingreso_manual_conciliacion(
    conciliacion_id: int,
    movimiento_clave: str,
    db: Session = Depends(get_db),
):
    conciliacion = buscar_conciliacion(db, conciliacion_id)
    try:
        eliminar_ingreso_manual(conciliacion_id, movimiento_clave)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    sincronizar_movimientos_auditados(conciliacion, db)
    return conciliacion_dict(buscar_conciliacion(db, conciliacion_id))


@router.post("/conciliaciones/{conciliacion_id}/egresos-manuales")
def crear_egreso_manual_conciliacion(
    conciliacion_id: int,
    entrada: ConciliacionEgresoManualEntrada,
    db: Session = Depends(get_db),
):
    conciliacion = buscar_conciliacion(db, conciliacion_id)
    item = next(
        (fila for fila in conciliacion.items if fila.id == entrada.item_id),
        None,
    )
    if item is None:
        raise HTTPException(
            status_code=400,
            detail="La pieza elegida no pertenece a esta conciliación",
        )
    agregar_egreso_manual(
        conciliacion_id=conciliacion_id,
        item_id=item.id,
        codigo=item.codigo,
        remito=entrada.remito,
        fecha=entrada.fecha,
        cantidad=entrada.cantidad,
        observacion=entrada.observacion,
    )
    sincronizar_movimientos_auditados(conciliacion, db)
    return conciliacion_dict(buscar_conciliacion(db, conciliacion_id))


@router.delete(
    "/conciliaciones/{conciliacion_id}/egresos-manuales/{movimiento_clave}"
)
def borrar_egreso_manual_conciliacion(
    conciliacion_id: int,
    movimiento_clave: str,
    db: Session = Depends(get_db),
):
    conciliacion = buscar_conciliacion(db, conciliacion_id)
    try:
        eliminar_egreso_manual(conciliacion_id, movimiento_clave)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    sincronizar_movimientos_auditados(conciliacion, db)
    return conciliacion_dict(buscar_conciliacion(db, conciliacion_id))


@router.delete("/conciliaciones/{conciliacion_id}", status_code=204)
def eliminar_conciliacion(
    conciliacion_id: int,
    db: Session = Depends(get_db),
):
    conciliacion = buscar_conciliacion(db, conciliacion_id)
    db.delete(conciliacion)
    db.commit()
    eliminar_auditoria(conciliacion_id)
    return Response(status_code=204)


@router.get("/busqueda/piezas")
def sugerir_piezas(
    q: str = Query(min_length=2, max_length=100),
    limite: int = Query(default=10, ge=1, le=20),
):
    return {
        "resultados": buscar_sugerencias_piezas(q, limite),
    }


@router.get("/busqueda/materiales")
def sugerir_materiales(
    q: str = Query(min_length=2, max_length=100),
    limite: int = Query(default=10, ge=1, le=20),
):
    return {
        "resultados": buscar_sugerencias_materiales(q, limite),
    }


@router.get("/piezas/{codigo}")
def obtener_pieza(codigo: str):
    pieza = buscar_pieza(codigo)
    if pieza is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"El código {normalizar_codigo(codigo)} "
                "no existe en produc01"
            ),
        )
    return pieza.to_dict()


@router.get("/materiales/{codigo}")
def obtener_material(codigo: str):
    material = buscar_material(codigo)
    if material is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"El código {normalizar_codigo(codigo)} "
                "no existe en mtprim01"
            ),
        )
    return material.to_dict()


@router.get("/estructuras/{codigo}")
def obtener_estructura(codigo: str):
    codigo = normalizar_codigo(codigo)
    if buscar_pieza(codigo) is None:
        raise HTTPException(
            status_code=404,
            detail=f"La pieza raíz {codigo} no existe en produc01",
        )
    try:
        nodos = obtener_estructura_recursiva(codigo)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {
        "codigo_raiz": codigo,
        "cantidad_codigos": len(nodos),
        "nodos": [nodo.to_dict() for nodo in nodos],
    }


@router.get("/plantillas/{plantilla_id}")
def obtener_plantilla(
    plantilla_id: int,
    db: Session = Depends(get_db),
):
    return plantilla_dict(buscar_plantilla(db, plantilla_id))


@router.post("/plantillas", status_code=201)
def crear_plantilla(
    entrada: PlantillaEntrada,
    db: Session = Depends(get_db),
):
    items_validados = validar_items_plantilla(entrada)
    tipo = db.get(TipoInventario, entrada.tipo_inventario_codigo)
    if tipo is None or not tipo.activo:
        raise HTTPException(
            status_code=422,
            detail="Seleccioná un tipo de inventario activo.",
        )
    if tipo.motor != entrada.categoria:
        raise HTTPException(
            status_code=422,
            detail="El tipo elegido no coincide con los artículos de la plantilla.",
        )

    ahora = datetime.now()
    plantilla = Plantilla(
        nombre=entrada.nombre.strip(),
        cliente=entrada.cliente.strip(),
        descripcion=entrada.descripcion.strip(),
        categoria=entrada.categoria,
        tipo_inventario_codigo=tipo.codigo,
        tipo_conteo=entrada.tipo_conteo,
        formato_impresion=entrada.formato_impresion,
        controla_remitos=entrada.controla_remitos,
        activa=entrada.activa,
        creada_en=ahora,
        actualizada_en=ahora,
    )
    plantilla.items = construir_items_plantilla(
        entrada.categoria,
        items_validados,
    )
    db.add(plantilla)
    db.commit()
    db.refresh(plantilla)
    return plantilla_dict(plantilla)


@router.put("/plantillas/{plantilla_id}")
def modificar_plantilla(
    plantilla_id: int,
    entrada: PlantillaEntrada,
    db: Session = Depends(get_db),
):
    plantilla = buscar_plantilla(db, plantilla_id)
    items_validados = validar_items_plantilla(entrada)
    tipo = db.get(TipoInventario, entrada.tipo_inventario_codigo)
    if tipo is None or not tipo.activo:
        raise HTTPException(
            status_code=422,
            detail="Seleccioná un tipo de inventario activo.",
        )
    if tipo.motor != entrada.categoria:
        raise HTTPException(
            status_code=422,
            detail="El tipo elegido no coincide con los artículos de la plantilla.",
        )

    plantilla.nombre = entrada.nombre.strip()
    plantilla.cliente = entrada.cliente.strip()
    plantilla.descripcion = entrada.descripcion.strip()
    plantilla.categoria = entrada.categoria
    plantilla.tipo_inventario_codigo = tipo.codigo
    plantilla.tipo_conteo = entrada.tipo_conteo
    plantilla.formato_impresion = entrada.formato_impresion
    plantilla.controla_remitos = entrada.controla_remitos
    plantilla.activa = entrada.activa
    plantilla.actualizada_en = datetime.now()
    plantilla.items = construir_items_plantilla(
        entrada.categoria,
        items_validados,
    )
    if not plantilla.activa:
        db.execute(
            update(ProgramacionInventario)
            .where(ProgramacionInventario.plantilla_id == plantilla.id)
            .values(activa=False)
        )

    db.commit()
    db.refresh(plantilla)
    return plantilla_dict(plantilla)


@router.delete("/plantillas/{plantilla_id}", status_code=204)
def eliminar_plantilla(
    plantilla_id: int,
    db: Session = Depends(get_db),
):
    plantilla = buscar_plantilla(db, plantilla_id)
    db.execute(
        update(Inventario)
        .where(Inventario.plantilla_id == plantilla.id)
        .values(plantilla_id=None)
    )
    db.delete(plantilla)
    db.commit()
    return Response(status_code=204)


@router.post("/programaciones", status_code=201)
def crear_programacion(
    entrada: ProgramacionEntrada,
    db: Session = Depends(get_db),
):
    plantilla = buscar_plantilla(db, entrada.plantilla_id)
    if not plantilla.activa:
        raise HTTPException(
            status_code=409,
            detail="La plantilla está inactiva y no se puede programar.",
        )
    programacion = ProgramacionInventario(
        plantilla_id=plantilla.id,
        fecha_proxima=entrada.fecha_proxima,
        frecuencia=entrada.frecuencia,
        dia_mes=entrada.fecha_proxima.day,
        mes_cierre_proximo=primer_dia_mes(entrada.mes_cierre_proximo),
        responsable=entrada.responsable.strip(),
        colaboradores=entrada.colaboradores.strip(),
        observaciones=entrada.observaciones.strip(),
        activa=True,
    )
    db.add(programacion)
    db.commit()
    guardar_mes_programacion(
        programacion.id,
        primer_dia_mes(entrada.mes_cierre_proximo),
    )
    return programacion_dict(buscar_programacion(db, programacion.id))


@router.put("/programaciones/{programacion_id}")
def modificar_programacion(
    programacion_id: int,
    entrada: ProgramacionEntrada,
    db: Session = Depends(get_db),
):
    programacion = buscar_programacion(db, programacion_id)
    plantilla = buscar_plantilla(db, entrada.plantilla_id)
    if not plantilla.activa:
        raise HTTPException(
            status_code=409,
            detail="La plantilla está inactiva y no se puede programar.",
        )
    programacion.plantilla_id = entrada.plantilla_id
    programacion.fecha_proxima = entrada.fecha_proxima
    programacion.frecuencia = entrada.frecuencia
    programacion.dia_mes = entrada.fecha_proxima.day
    programacion.mes_cierre_proximo = primer_dia_mes(
        entrada.mes_cierre_proximo
    )
    programacion.responsable = entrada.responsable.strip()
    programacion.colaboradores = entrada.colaboradores.strip()
    programacion.observaciones = entrada.observaciones.strip()
    programacion.activa = True
    db.commit()
    guardar_mes_programacion(
        programacion.id,
        primer_dia_mes(entrada.mes_cierre_proximo),
    )
    return programacion_dict(buscar_programacion(db, programacion.id))


@router.post("/programaciones/{programacion_id}/alternar")
def alternar_programacion(
    programacion_id: int,
    db: Session = Depends(get_db),
):
    programacion = buscar_programacion(db, programacion_id)
    if (
        not programacion.activa
        and programacion.frecuencia == "UNA_VEZ"
        and programacion.ultima_ejecucion
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "La programación de una sola vez ya fue completada. "
                "Editala para asignarle una nueva fecha."
            ),
        )
    if not programacion.activa and not programacion.plantilla.activa:
        raise HTTPException(
            status_code=409,
            detail=(
                "La plantilla está inactiva. Reactivala antes de "
                "reanudar esta programación."
            ),
        )
    programacion.activa = not programacion.activa
    db.commit()
    return programacion_dict(buscar_programacion(db, programacion.id))


@router.delete("/programaciones/{programacion_id}", status_code=204)
def eliminar_programacion(
    programacion_id: int,
    db: Session = Depends(get_db),
):
    programacion = buscar_programacion(db, programacion_id)
    for inventario in programacion.inventarios:
        inventario.programacion_id = None
    db.delete(programacion)
    db.commit()
    eliminar_mes_programacion(programacion_id)
    return Response(status_code=204)


@router.post("/inventarios", status_code=201)
def crear_inventario(
    entrada: InventarioEntrada,
    db: Session = Depends(get_db),
):
    plantilla: Plantilla | None = None
    pieza_raiz = None
    es_ciclico_directo = entrada.modo == "CICLICO"
    es_manual = entrada.modo == "MANUAL"
    items_manual: list[InventarioItem] = []
    tipo_solicitado = (
        db.get(TipoInventario, entrada.tipo_inventario_codigo)
        if entrada.tipo_inventario_codigo
        else None
    )
    modalidad_solicitada = (
        tipo_solicitado.modalidad
        if tipo_solicitado is not None
        else entrada.modalidad_conteo
    )

    if es_ciclico_directo:
        codigo_raiz = normalizar_codigo(entrada.codigo_raiz)
        if not codigo_raiz:
            raise HTTPException(
                status_code=422,
                detail="Ingresá la pieza raíz del inventario cíclico",
            )
        pieza_raiz = buscar_pieza(codigo_raiz)
        if pieza_raiz is None:
            raise HTTPException(
                status_code=422,
                detail=f"La pieza raíz {codigo_raiz} no existe en produc01",
            )
        cliente = (
            pieza_raiz.codigo_cliente.strip()
            or "Inventario cíclico"
        )
        plantilla_id = None
        categoria = "CICLICO"
        formato_impresion = "CICLICO"
        controla_remitos = entrada.controla_remitos
    elif es_manual:
        entradas_manuales = list(entrada.articulos_manual)
        if not entradas_manuales and entrada.codigo_manual.strip():
            entradas_manuales = [
                ArticuloInventarioEntrada(
                    codigo=entrada.codigo_manual,
                    tipo_articulo=entrada.tipo_articulo_manual,
                    contar_material=entrada.contar_material,
                )
            ]
        if not entradas_manuales:
            raise HTTPException(
                status_code=422,
                detail="Agregá al menos un código al inventario manual",
            )
        tipos_manual = {
            articulo.tipo_articulo for articulo in entradas_manuales
        }
        if len(tipos_manual) != 1:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Un inventario manual debe contener sólo piezas "
                    "o sólo materias primas."
                ),
            )
        codigos_vistos: set[str] = set()
        articulos_validados = []
        for articulo_entrada in entradas_manuales:
            codigo = normalizar_codigo(articulo_entrada.codigo)
            if codigo in codigos_vistos:
                raise HTTPException(
                    status_code=422,
                    detail=f"El código {codigo} está repetido en el listado",
                )
            codigos_vistos.add(codigo)
            articulo, nuevos_items = construir_items_articulo(
                articulo_entrada,
                tipo_conteo=entrada.tipo_conteo,
                modalidad_conteo=modalidad_solicitada,
            )
            articulos_validados.append(articulo)
            items_manual.extend(nuevos_items)

        if "MATERIA_PRIMA" in tipos_manual:
            categoria = "MATERIA_PRIMA"
            cliente = "Inventario manual de MP"
            formato_impresion = "LISTADO_SIMPLE"
        else:
            categoria = "PIEZAS"
            clientes = {
                articulo.codigo_cliente.strip()
                for articulo in articulos_validados
                if articulo.codigo_cliente.strip()
            }
            cliente = (
                next(iter(clientes))
                if len(clientes) == 1
                else "Inventario manual"
            )
            formato_impresion = "FLUJO_HORIZONTAL"
        plantilla_id = None
        controla_remitos = entrada.controla_remitos
    else:
        if entrada.plantilla_id is None:
            raise HTTPException(
                status_code=422,
                detail="Seleccioná una plantilla",
            )
        plantilla = db.scalar(
            select(Plantilla)
            .where(Plantilla.id == entrada.plantilla_id)
            .options(selectinload(Plantilla.items))
        )
        if plantilla is None:
            raise HTTPException(
                status_code=404,
                detail="Plantilla no encontrada",
            )
        if not plantilla.activa:
            raise HTTPException(
                status_code=409,
                detail=(
                    "La plantilla está inactiva. Reactivala antes de "
                    "generar un inventario."
                ),
            )
        cliente = plantilla.cliente
        plantilla_id = plantilla.id
        categoria = plantilla.categoria
        formato_impresion = plantilla.formato_impresion
        controla_remitos = plantilla.controla_remitos

    if plantilla is not None:
        tipo_codigo = plantilla.tipo_inventario_codigo
        tipo = db.get(TipoInventario, tipo_codigo)
    elif tipo_solicitado is not None:
        tipo = tipo_solicitado
        tipo_codigo = tipo.codigo
    elif es_ciclico_directo:
        tipo = db.get(TipoInventario, "CICLICO")
        tipo_codigo = "CICLICO"
    elif categoria == "MATERIA_PRIMA":
        tipo = db.get(TipoInventario, "MATERIA_PRIMA")
        tipo_codigo = "MATERIA_PRIMA"
    elif entrada.modalidad_conteo == "MEDIOS":
        tipo = db.get(TipoInventario, "MEDIOS")
        tipo_codigo = "MEDIOS"
    else:
        tipo = db.get(TipoInventario, "PIEZAS_PROCESO")
        tipo_codigo = "PIEZAS_PROCESO"

    if tipo is None or not tipo.activo:
        raise HTTPException(
            status_code=422,
            detail="El tipo de inventario seleccionado no está disponible.",
        )
    motor_esperado = "CICLICO" if es_ciclico_directo else categoria
    if tipo.motor != motor_esperado:
        raise HTTPException(
            status_code=422,
            detail="El tipo de inventario no corresponde al origen seleccionado.",
        )
    modalidad_conteo = tipo.modalidad
    if tipo.formato_impresion:
        formato_impresion = tipo.formato_impresion

    if modalidad_conteo == "MEDIOS" and categoria != "PIEZAS":
        raise HTTPException(
            status_code=422,
            detail=(
                "El conteo de medios sólo puede usarse con piezas "
                "terminadas de produc01."
            ),
        )
    if modalidad_conteo == "MEDIOS" and es_ciclico_directo:
        raise HTTPException(
            status_code=422,
            detail="El conteo de medios no corresponde a un inventario cíclico.",
        )
    if modalidad_conteo == "MEDIOS":
        formato_impresion = "MEDIOS"

    ultimo_id = db.scalar(select(func.max(Inventario.id))) or 0
    codigo = f"INV-{entrada.fecha.year}-{ultimo_id + 12:03d}"
    inventario = Inventario(
        codigo=codigo,
        origen=entrada.modo,
        cliente=cliente,
        plantilla_id=plantilla_id,
        fecha=entrada.fecha,
        mes_cierre=primer_dia_mes(entrada.mes_cierre),
        responsable=entrada.responsable.strip(),
        colaboradores=entrada.colaboradores.strip(),
        ambito=entrada.ambito,
        estado="En preparación",
        categoria=categoria,
        tipo_inventario_codigo=tipo_codigo,
        modalidad_conteo=modalidad_conteo,
        formato_impresion=formato_impresion,
        formato_version_id=version_actual_id(db, formato_impresion),
        controla_remitos=controla_remitos,
        observaciones=entrada.observaciones.strip(),
        stock_actualizado_en=datetime.now(),
        stock_origen=fuente_stock_actual(),
    )
    items_inventario: list[InventarioItem] = []

    if es_ciclico_directo or (
        plantilla is not None and plantilla.categoria == "CICLICO"
    ):
        if not es_ciclico_directo and not plantilla.items:
            raise HTTPException(
                status_code=409,
                detail="La plantilla cíclica no tiene una pieza raíz",
            )
        codigo_raiz = (
            normalizar_codigo(entrada.codigo_raiz)
            if es_ciclico_directo
            else plantilla.items[0].codigo
        )
        tipo_conteo_ciclico = (
            entrada.tipo_conteo
            if es_ciclico_directo
            else plantilla.tipo_conteo
        )
        ubicacion_raiz = (
            ""
            if es_ciclico_directo
            else plantilla.items[0].ubicacion
        )
        try:
            nodos = obtener_estructura_recursiva(codigo_raiz)
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        codigos_estructura = {nodo.codigo for nodo in nodos}
        materiales_agregados: set[str] = set()
        materiales_inferidos: dict[str, dict] = {}
        for nodo in nodos:
            pieza = buscar_pieza(nodo.codigo)
            if pieza is not None:
                agregar_pieza_ciclica(
                    items_inventario,
                    pieza,
                    tipo_conteo=tipo_conteo_ciclico,
                    codigo_padre=nodo.codigo_padre,
                    nivel=nodo.nivel,
                    uso=nodo.uso_acumulado,
                    ruta=nodo.ruta,
                    ubicacion=ubicacion_raiz if nodo.nivel == 0 else "",
                )

                codigo_material = normalizar_codigo(
                    pieza.codigo_material
                )
                if (
                    codigo_material
                    and codigo_material not in codigos_estructura
                    and codigo_material not in materiales_agregados
                ):
                    material = buscar_material(codigo_material)
                    if material is not None:
                        inferido = materiales_inferidos.setdefault(
                            material.codigo,
                            {
                                "material": material,
                                "codigo_padre": pieza.codigo,
                                "nivel": nodo.nivel + 1,
                                "uso": 0,
                                "ruta": (
                                    f"{nodo.ruta} > {material.codigo}"
                                ),
                            },
                        )
                        inferido["uso"] += nodo.uso_acumulado
                continue

            material = buscar_material(nodo.codigo)
            if material is not None:
                if material.codigo not in materiales_agregados:
                    agregar_material_ciclico(
                        items_inventario,
                        material,
                        codigo_padre=nodo.codigo_padre,
                        nivel=nodo.nivel,
                        uso=nodo.uso_acumulado,
                        ruta=nodo.ruta,
                    )
                    materiales_agregados.add(material.codigo)
                continue

            raise HTTPException(
                status_code=409,
                detail=(
                    f"El código {nodo.codigo} de produc10 no existe "
                    "en produc01 ni en mtprim01"
                ),
            )

        for datos in materiales_inferidos.values():
            if datos["material"].codigo in materiales_agregados:
                continue
            agregar_material_ciclico(
                items_inventario,
                datos["material"],
                codigo_padre=datos["codigo_padre"],
                nivel=datos["nivel"],
                uso=datos["uso"],
                ruta=datos["ruta"],
            )

        if modalidad_conteo == "MEDIOS":
            items_inventario = [
                item for item in items_inventario
                if item.etapa == "TERMINADO"
            ]
        inventario.items = items_inventario
        db.add(inventario)
        db.commit()
        db.refresh(inventario)
        guardar_mes_inventario(inventario.id, entrada.mes_cierre)
        return inventario_dict(inventario)

    if es_manual:
        if categoria == "PIEZAS":
            materiales_vistos: set[tuple[str, str]] = set()
            items_sin_mp_duplicada = []
            for item in items_manual:
                if item.etapa != "MATERIAL":
                    items_sin_mp_duplicada.append(item)
                    continue
                clave_material = (
                    normalizar_codigo(item.codigo_material or item.codigo),
                    item.lote,
                )
                if clave_material in materiales_vistos:
                    continue
                materiales_vistos.add(clave_material)
                items_sin_mp_duplicada.append(item)
            items_manual = items_sin_mp_duplicada
        items_inventario.extend(items_manual)
        inventario.items = items_inventario
        db.add(inventario)
        db.commit()
        db.refresh(inventario)
        guardar_mes_inventario(inventario.id, entrada.mes_cierre)
        return inventario_dict(inventario)

    if plantilla.categoria == "MATERIA_PRIMA":
        for item in plantilla.items:
            material = buscar_material(item.codigo)
            if material is None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"El material {item.codigo} ya no existe en mtprim01. "
                        "Revisá la plantilla."
                    ),
                )

            lotes = material.lotes or [None]
            for lote in lotes:
                items_inventario.append(
                    InventarioItem(
                        codigo=material.codigo,
                        codigo_material=material.codigo,
                        descripcion=material.descripcion,
                        ubicacion=item.ubicacion,
                        diametro=material.diametro,
                        largo=material.largo,
                        espesor=material.espesor,
                        unidad=material.unidad,
                        lote=lote.lote if lote else "",
                        etapa="MATERIAL",
                        operacion=lote.lote if lote else "",
                        titulo_operacion=(
                            titulo_lote_material(lote.lote, material.descripcion)
                            if lote and lote.lote
                            else titulo_lote_material("", material.descripcion)
                        ),
                        stock_sistema=lote.stock if lote else 0,
                    )
                )

        inventario.items = items_inventario
        db.add(inventario)
        db.commit()
        db.refresh(inventario)
        guardar_mes_inventario(inventario.id, entrada.mes_cierre)
        return inventario_dict(inventario)

    materiales_pieza_agregados: set[str] = set()
    for item in plantilla.items:
        pieza = buscar_pieza(item.codigo)
        if pieza is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"El código {item.codigo} ya no existe en produc01. "
                    "Revisá la plantilla."
                ),
            )

        comunes = {
            "codigo": pieza.codigo,
            "codigo_cliente": pieza.codigo_cliente,
            "codigo_material": pieza.codigo_material,
            "descripcion": pieza.descripcion,
            "ubicacion": item.ubicacion,
            "contar_material": item.contar_material,
            "tipo_estructura": pieza.tipo_estructura,
        }

        # La fila de MP se crea solamente cuando la pieza tiene MATE_ y la
        # plantilla indica expresamente que ese material debe contarse.
        codigo_material = normalizar_codigo(pieza.codigo_material)
        if (
            item.contar_material
            and codigo_material
            and codigo_material not in materiales_pieza_agregados
        ):
            items_inventario.extend(
                construir_filas_material_pieza(pieza, comunes)
            )
            materiales_pieza_agregados.add(codigo_material)

        if pieza.tiene_operaciones_maestro:
            if plantilla.tipo_conteo == "POR_OPERACION":
                items_inventario.extend(
                    InventarioItem(
                        **comunes,
                        etapa="OPERACION",
                        operacion=operacion.operacion,
                        titulo_operacion=operacion.titulo,
                        proveedor=operacion.proveedores,
                        stock_sistema=operacion.stock,
                    )
                    for operacion in pieza.operaciones
                )
            else:
                items_inventario.append(
                    InventarioItem(
                        **comunes,
                        etapa="PROCESO_GLOBAL",
                        operacion="TOTAL",
                        titulo_operacion="Total en proceso",
                        proveedor=pieza.proveedores_proceso,
                        stock_sistema=pieza.stock_proceso_total,
                    )
                )

        items_inventario.append(
            InventarioItem(
                **comunes,
                etapa="TERMINADO",
                titulo_operacion="Pieza terminada",
                stock_sistema=pieza.stock_terminado,
            )
        )

    if not items_inventario:
        raise HTTPException(
            status_code=422,
            detail="La plantilla no generó filas para inventariar.",
        )

    if modalidad_conteo == "MEDIOS":
        items_inventario = [
            item for item in items_inventario
            if item.etapa == "TERMINADO"
        ]
    inventario.items = items_inventario
    db.add(inventario)
    db.commit()
    db.refresh(inventario)
    guardar_mes_inventario(inventario.id, entrada.mes_cierre)
    return inventario_dict(inventario)


@router.post("/programaciones/{programacion_id}/generar", status_code=201)
def generar_inventario_programado(
    programacion_id: int,
    db: Session = Depends(get_db),
):
    programacion = buscar_programacion(db, programacion_id)
    hoy = date.today()
    if not programacion.activa:
        raise HTTPException(
            status_code=409,
            detail="La programación está pausada o ya fue completada",
        )
    if not programacion.plantilla.activa:
        raise HTTPException(
            status_code=409,
            detail="La plantilla está inactiva.",
        )
    fecha_programada = programacion.fecha_proxima
    mes_cierre = programacion.mes_cierre_proximo or primer_dia_mes(
        fecha_programada
    )
    if programacion.frecuencia == "MENSUAL":
        if existe_cierre_programacion(programacion.id, mes_cierre):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Esta programación mensual ya generó un inventario "
                    "para ese mes de cierre. Corregí el mes antes de continuar."
                ),
            )
    inventario_creado = crear_inventario(
        InventarioEntrada(
            plantilla_id=programacion.plantilla_id,
            fecha=hoy,
            mes_cierre=mes_cierre,
            responsable=programacion.responsable,
            colaboradores=programacion.colaboradores,
            observaciones=programacion.observaciones,
        ),
        db,
    )
    inventario = db.get(Inventario, inventario_creado["id"])
    inventario.programacion_id = programacion.id
    inventario.fecha_programada = fecha_programada
    inventario.mes_cierre = primer_dia_mes(mes_cierre)
    avanzar_programacion(programacion, hoy)
    db.commit()
    guardar_mes_inventario(inventario.id, mes_cierre)
    vincular_inventario_programacion(inventario.id, programacion.id)
    guardar_mes_programacion(
        programacion.id,
        programacion.mes_cierre_proximo,
    )

    inventario = buscar_inventario(db, inventario.id)
    programacion = buscar_programacion(db, programacion.id)
    return {
        "inventario": inventario_dict(inventario),
        "programacion": programacion_dict(programacion),
    }


def datos_base_item(item: InventarioItem, **cambios) -> dict:
    datos = {
        "codigo": item.codigo,
        "codigo_cliente": item.codigo_cliente,
        "codigo_material": item.codigo_material,
        "descripcion": item.descripcion,
        "ubicacion": item.ubicacion,
        "diametro": item.diametro,
        "largo": item.largo,
        "espesor": item.espesor,
        "unidad": item.unidad,
        "codigo_padre": item.codigo_padre,
        "nivel": item.nivel,
        "uso": item.uso,
        "ruta": item.ruta,
        "tipo_estructura": item.tipo_estructura,
        "contar_material": item.contar_material,
    }
    datos.update(cambios)
    return datos


def actualizar_filas_material(
    inventario: Inventario,
    codigo: str,
    material,
) -> None:
    filas = [
        item
        for item in inventario.items
        if item.codigo == codigo and item.etapa == "MATERIAL"
    ]
    if not filas:
        return

    lotes = {lote.lote: lote.stock for lote in material.lotes}
    if lotes and len(filas) == 1:
        marcador_vacio = filas[0]
        if not marcador_vacio.lote and marcador_vacio.conteo_fisico is None:
            primer_lote = next(iter(lotes))
            marcador_vacio.lote = primer_lote
            marcador_vacio.operacion = primer_lote

    filas_por_lote = {item.lote: item for item in filas}
    for item in filas:
        item.descripcion = material.descripcion
        item.diametro = material.diametro
        item.largo = material.largo
        item.espesor = material.espesor
        item.unidad = material.unidad
        item.stock_sistema = float(lotes.get(item.lote, 0))
        item.titulo_operacion = titulo_lote_material(
            item.lote,
            material.descripcion,
        )
        item.stock_pendiente = False

    base = filas[0]
    for lote, stock in lotes.items():
        if lote in filas_por_lote:
            continue
        inventario.items.append(
            InventarioItem(
                **datos_base_item(
                    base,
                    codigo=material.codigo,
                    codigo_material=material.codigo,
                    descripcion=material.descripcion,
                    diametro=material.diametro,
                    largo=material.largo,
                    espesor=material.espesor,
                    unidad=material.unidad,
                ),
                lote=lote,
                etapa="MATERIAL",
                operacion=lote,
                titulo_operacion=titulo_lote_material(
                    lote,
                    material.descripcion,
                ),
                stock_sistema=float(stock),
                stock_pendiente=False,
            )
        )


def actualizar_filas_material_compartido(
    inventario: Inventario,
    pieza,
) -> None:
    codigo_material = normalizar_codigo(pieza.codigo_material)
    filas = [
        item for item in inventario.items
        if (
            item.etapa == "MATERIAL"
            and normalizar_codigo(item.codigo_material or item.codigo)
            == codigo_material
        )
    ]
    if not filas:
        return
    lotes = {
        lote.lote: float(lote.stock)
        for lote in (pieza.lotes_material or [])
    }
    if lotes and any(
        not item.lote and item.conteo_fisico is not None
        for item in filas
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"La MP {codigo_material} tiene un conteo total sin lote. "
                "Borrá ese conteo antes de actualizarla por lotes."
            ),
        )

    descripcion_material = (
        str(getattr(pieza, "descripcion_material", "") or "").strip()
        or pieza.codigo_material
    )
    unidad_material = str(
        getattr(pieza, "unidad_material", "") or ""
    ).strip()
    codigo_propietario = filas[0].codigo
    filas_ordenadas = sorted(
        filas,
        key=lambda item: (
            item.codigo != codigo_propietario,
            item.id is None,
            item.id or 0,
        ),
    )
    if lotes and len(filas) == 1 and not filas[0].lote:
        primer_lote = next(iter(lotes))
        filas[0].lote = primer_lote
        filas[0].operacion = primer_lote

    lotes_asignados: set[str] = set()
    for item in filas_ordenadas:
        item.codigo_material = codigo_material
        if unidad_material:
            item.unidad = unidad_material
        if item.lote in lotes and item.lote not in lotes_asignados:
            item.stock_sistema = float(lotes[item.lote])
            lotes_asignados.add(item.lote)
        else:
            # Una MP compartida pertenece al grupo, no a cada pieza. Las
            # filas heredadas se conservan para no perder conteos, pero su
            # stock no vuelve a sumarse.
            item.stock_sistema = 0
        item.titulo_operacion = titulo_lote_material(
            item.lote,
            descripcion_material,
        )
        item.stock_pendiente = False

    base = filas_ordenadas[0]
    for lote, stock in lotes.items():
        if lote in lotes_asignados:
            continue
        datos = datos_base_item(
            base,
            codigo=codigo_propietario,
            codigo_material=codigo_material,
        )
        if unidad_material:
            datos["unidad"] = unidad_material
        inventario.items.append(InventarioItem(
            **datos,
            lote=lote,
            etapa="MATERIAL",
            operacion=lote,
            titulo_operacion=titulo_lote_material(
                lote,
                descripcion_material,
            ),
            stock_sistema=float(stock),
            stock_pendiente=False,
        ))


def actualizar_stock_piezas(
    inventario: Inventario,
    codigos_pieza: set[str],
) -> None:
    materiales_actualizados: set[str] = set()
    for codigo in sorted(codigos_pieza):
        pieza = buscar_pieza(codigo)
        if pieza is None:
            raise HTTPException(
                status_code=409,
                detail=f"El código {codigo} ya no existe en produc01",
            )
        filas = [item for item in inventario.items if item.codigo == codigo]
        stock_asignado = sum(
            float(item.stock_asignado or 0)
            for item in filas
            if item.etapa in {
                "TERMINADO",
                "OPERACION",
                "PROCESO_GLOBAL",
            }
        )
        operaciones_por_codigo = {
            operacion.operacion: operacion
            for operacion in pieza.operaciones
        }
        codigo_material = normalizar_codigo(pieza.codigo_material)
        if codigo_material and codigo_material not in materiales_actualizados:
            actualizar_filas_material_compartido(inventario, pieza)
            materiales_actualizados.add(codigo_material)
        for item in filas:
            item.tipo_estructura = (
                "PADRE"
                if inventario.categoria == "CICLICO" and item.nivel == 0
                else (
                    "HIJO"
                    if (
                        inventario.categoria == "CICLICO"
                        and pieza.tipo_estructura == "INDEPENDIENTE"
                    )
                    else pieza.tipo_estructura
                )
            )
            if item.etapa == "MATERIAL":
                continue
            elif item.etapa == "PROCESO_GLOBAL":
                item.stock_sistema = pieza.stock_proceso_total
                item.proveedor = pieza.proveedores_proceso
            elif item.etapa == "OPERACION":
                operacion = operaciones_por_codigo.get(item.operacion)
                item.stock_sistema = operacion.stock if operacion else 0
                item.proveedor = operacion.proveedores if operacion else ""
                if operacion:
                    item.titulo_operacion = operacion.titulo
            elif item.etapa == "TERMINADO":
                item.stock_sistema = pieza.stock_terminado
            item.stock_pendiente = False

        filas_operacion = [
            item for item in filas if item.etapa == "OPERACION"
        ]
        if filas_operacion:
            existentes = {item.operacion for item in filas_operacion}
            base = filas[0]
            for operacion in pieza.operaciones:
                if operacion.operacion in existentes:
                    continue
                inventario.items.append(
                    InventarioItem(
                        **datos_base_item(base),
                        etapa="OPERACION",
                        operacion=operacion.operacion,
                        titulo_operacion=operacion.titulo,
                        proveedor=operacion.proveedores,
                        stock_sistema=operacion.stock,
                        stock_pendiente=False,
                    )
                )
        aplicar_stock_asignado(
            [item for item in inventario.items if item.codigo == codigo],
            stock_asignado,
        )

        base = filas[0]
        if (
            base.contar_material
            and codigo_material
            and not any(
                item.etapa == "MATERIAL"
                and normalizar_codigo(item.codigo_material or item.codigo)
                == codigo_material
                for item in inventario.items
            )
        ):
            inventario.items.extend(
                construir_filas_material_pieza(
                    pieza,
                    datos_base_item(
                        base,
                        codigo_material=pieza.codigo_material,
                    ),
                )
            )


@router.post("/inventarios/{inventario_id}/actualizar-stock")
def actualizar_stock_inventario(
    inventario_id: int,
    entrada: ConteoEntrada,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado == "Cerrado":
        raise HTTPException(
            status_code=409,
            detail="El stock de un inventario cerrado no puede modificarse",
        )

    aplicar_conteos_recibidos(inventario, entrada, db)

    codigos_pieza = {
        item.codigo
        for item in inventario.items
        if item.etapa in {"OPERACION", "PROCESO_GLOBAL", "TERMINADO"}
    }
    actualizar_stock_piezas(inventario, codigos_pieza)

    codigos_material = {
        item.codigo
        for item in inventario.items
        if item.etapa == "MATERIAL" and item.codigo not in codigos_pieza
    }
    for codigo in sorted(codigos_material):
        material = buscar_material(codigo)
        if material is None:
            raise HTTPException(
                status_code=409,
                detail=f"El material {codigo} ya no existe en mtprim01",
            )
        actualizar_filas_material(inventario, codigo, material)

    if (
        inventario.estado == "En preparación"
        and any(item.conteo_fisico is not None for item in inventario.items)
    ):
        inventario.estado = "En conteo"
    inventario.stock_actualizado_en = datetime.now()
    inventario.stock_origen = fuente_stock_actual()
    db.commit()
    sincronizar_bases(
        inventario.id,
        {item.id: item.conteo_fisico for item in inventario.items},
    )
    return inventario_dict(buscar_inventario(db, inventario.id))


def aplicar_conteos_recibidos(
    inventario: Inventario,
    entrada: ConteoEntrada,
    db: Session,
) -> None:
    revision_recibida = entrada.revision_conteo
    if revision_recibida is not None and revision_recibida.tzinfo is not None:
        revision_recibida = revision_recibida.replace(tzinfo=None)
    revision_actual_texto = obtener_revision(inventario.id)
    revision_actual = (
        datetime.fromisoformat(revision_actual_texto)
        if revision_actual_texto
        else None
    )
    if revision_actual != revision_recibida:
        raise HTTPException(
            status_code=409,
            detail=(
                "El conteo cambió desde otro equipo o celular. "
                "Volvé a abrir el inventario antes de guardar."
            ),
        )
    if entrada.ambito is not None:
        inventario.ambito = entrada.ambito
    if entrada.observaciones is not None:
        inventario.observaciones = entrada.observaciones.strip()
    items_por_id = {item.id: item for item in inventario.items}
    for conteo in entrada.items:
        item = items_por_id.get(conteo.item_id)
        if item is None:
            raise HTTPException(
                status_code=400,
                detail=f"El ítem {conteo.item_id} no pertenece al inventario",
            )
        if inventario.modalidad_conteo == "MEDIOS":
            desglose = (
                conteo.conteo_vacios,
                conteo.conteo_llenos,
                conteo.conteo_rotos,
            )
            valores_presentes = sum(valor is not None for valor in desglose)
            if valores_presentes not in {0, 3}:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Completá Vacíos, Llenos y Rotos para cada medio "
                        "o dejá los tres campos sin completar."
                    ),
                )
            item.conteo_vacios = conteo.conteo_vacios
            item.conteo_llenos = conteo.conteo_llenos
            item.conteo_rotos = conteo.conteo_rotos
            item.conteo_fisico = (
                sum(desglose)
                if valores_presentes == 3
                else None
            )
        else:
            item.conteo_fisico = conteo.conteo_fisico
        causa_codigo = (
            (conteo.causa_diferencia_codigo or "").strip().upper()
            or None
        )
        if (
            causa_codigo is not None
            and db.get(CausaDiferencia, causa_codigo) is None
        ):
            raise HTTPException(
                status_code=422,
                detail=f"La causa {causa_codigo} no está configurada",
            )
        item.causa_diferencia_codigo = causa_codigo
        metrica = metricas_conteo_item(item)
        requiere_ajuste = metrica["dentro_tolerancia"] is False
        ajustado_sistema = (
            conteo.ajustado_sistema if requiere_ajuste else False
        )
        if ajustado_sistema != item.ajustado_sistema:
            item.ajustado_sistema_en = (
                datetime.now()
                if ajustado_sistema
                else None
            )
        item.ajustado_sistema = ajustado_sistema
        item.observaciones = conteo.observaciones.strip()
    if inventario.controla_remitos:
        inventario.ultimo_remito_ingreso = (
            entrada.ultimo_remito_ingreso or ""
        ).strip()
        inventario.ultimo_remito_egreso = (
            entrada.ultimo_remito_egreso or ""
        ).strip()
def validar_reporte_necesario(
    reporte,
    necesario: bool,
    nombre: str,
) -> None:
    if necesario and reporte is None:
        raise HTTPException(
            status_code=422,
            detail=f"Este inventario necesita el reporte {nombre}",
        )


def aplicar_stock_asignado(
    filas: list[InventarioItem],
    cantidad: float,
) -> None:
    """
    Suma el stock asignado una sola vez al stock terminado.

    El reporte ASIGNADO es independiente del reporte de piezas en proceso y de
    las operaciones configuradas. Por eso siempre se aplica a TERMINADO y se
    limpian los valores heredados que versiones anteriores podían haber dejado
    en OPERACION o PROCESO_GLOBAL.
    """
    for item in filas:
        item.stock_asignado = 0

    filas_terminado = [item for item in filas if item.etapa == "TERMINADO"]
    if not filas_terminado:
        return

    destino = min(
        filas_terminado,
        key=lambda item: item.id or 0,
    )
    destino.stock_asignado = float(cantidad or 0)
    destino.stock_sistema += destino.stock_asignado


def actualizar_piezas_desde_excel(
    inventario: Inventario,
    reporte_pt,
    reporte_prd,
    reporte_asignado,
) -> dict:
    codigos_pieza = {
        item.codigo
        for item in inventario.items
        if item.etapa in {"OPERACION", "PROCESO_GLOBAL", "TERMINADO"}
    }
    faltantes_pt = []
    faltantes_prd = []
    faltantes_asignado = []
    for codigo in sorted(codigos_pieza):
        filas = [item for item in inventario.items if item.codigo == codigo]
        asignado_anterior = sum(
            float(item.stock_asignado or 0)
            for item in filas
            if item.etapa in {
                "TERMINADO",
                "OPERACION",
                "PROCESO_GLOBAL",
            }
        )
        stock_asignado = (
            reporte_asignado.asignado.get(codigo, 0)
            if reporte_asignado
            else asignado_anterior
        )
        datos_prd = reporte_prd.prd.get(codigo, {}) if reporte_prd else {}
        if reporte_pt and codigo not in reporte_pt.pt:
            faltantes_pt.append(codigo)
        if reporte_prd and codigo not in reporte_prd.prd:
            faltantes_prd.append(codigo)
        if reporte_asignado and codigo not in reporte_asignado.asignado:
            faltantes_asignado.append(codigo)

        for item in filas:
            if item.etapa == "TERMINADO":
                item.stock_sistema = reporte_pt.pt.get(codigo, 0)
            elif item.etapa == "PROCESO_GLOBAL":
                item.stock_sistema = sum(
                    dato.cantidad for dato in datos_prd.values()
                )
                proveedores = sorted({
                    proveedor
                    for dato in datos_prd.values()
                    for proveedor in dato.proveedores
                })
                item.proveedor = ", ".join(proveedores)
            elif item.etapa == "OPERACION":
                dato = datos_prd.get(item.operacion)
                item.stock_sistema = dato.cantidad if dato else 0
                item.proveedor = proveedores_texto(dato) if dato else ""
            item.stock_pendiente = False

        filas_operacion = [
            item for item in filas if item.etapa == "OPERACION"
        ]
        if filas_operacion:
            existentes = {item.operacion for item in filas_operacion}
            base = filas[0]
            for operacion, dato in datos_prd.items():
                if operacion in existentes:
                    continue
                inventario.items.append(
                    InventarioItem(
                        **datos_base_item(base),
                        etapa="OPERACION",
                        operacion=operacion,
                        titulo_operacion="Operación importada desde Excel",
                        proveedor=proveedores_texto(dato),
                        stock_sistema=dato.cantidad,
                        stock_pendiente=False,
                    )
                )
        aplicar_stock_asignado(
            [item for item in inventario.items if item.codigo == codigo],
            stock_asignado,
        )
    return {
        "codigos_pieza": len(codigos_pieza),
        "sin_registro_pt": faltantes_pt,
        "sin_registro_prd": faltantes_prd,
        "sin_registro_asignado": faltantes_asignado,
    }


def actualizar_materiales_desde_excel(
    inventario: Inventario,
    reporte_mp,
) -> dict:
    codigos_pieza = {
        item.codigo
        for item in inventario.items
        if item.etapa in {"OPERACION", "PROCESO_GLOBAL", "TERMINADO"}
    }
    grupos: dict[str, list[InventarioItem]] = {}
    for item in inventario.items:
        if item.etapa != "MATERIAL":
            continue
        codigo_material = normalizar_codigo(item.codigo_material or item.codigo)
        grupos.setdefault(codigo_material, []).append(item)

    faltantes_mp = []
    for codigo_material, filas in grupos.items():
        lotes_reporte = reporte_mp.mp.get(codigo_material, {})
        if not lotes_reporte:
            faltantes_mp.append(codigo_material)
        if lotes_reporte and any(
            not item.lote and item.conteo_fisico is not None
            for item in filas
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"La MP {codigo_material} tiene un conteo total sin lote. "
                    "Borrá ese conteo antes de "
                    "importar el nuevo reporte por lotes."
                ),
            )

        codigo_propietario = filas[0].codigo
        filas_ordenadas = sorted(
            filas,
            key=lambda item: (
                item.codigo != codigo_propietario,
                item.id is None,
                item.id or 0,
            ),
        )
        if lotes_reporte and len(filas) == 1 and not filas[0].lote:
            primer_lote = next(iter(lotes_reporte))
            filas[0].lote = primer_lote
            filas[0].operacion = primer_lote

        es_pieza = codigo_propietario in codigos_pieza
        lotes_asignados: set[str] = set()
        for item in filas_ordenadas:
            dato = lotes_reporte.get(item.lote)
            if dato and item.lote not in lotes_asignados:
                item.stock_sistema = float(dato.cantidad)
                lotes_asignados.add(item.lote)
            else:
                item.stock_sistema = 0
            if dato and dato.unidad:
                item.unidad = dato.unidad
            if dato and dato.descripcion and not es_pieza:
                item.descripcion = dato.descripcion
            item.titulo_operacion = titulo_lote_material(
                item.lote,
                dato.descripcion if dato else "",
            )
            item.stock_pendiente = False

        base = filas_ordenadas[0]
        for lote, dato in lotes_reporte.items():
            if lote in lotes_asignados:
                continue
            datos = datos_base_item(
                base,
                codigo=codigo_propietario,
                codigo_material=codigo_material,
            )
            if dato.unidad:
                datos["unidad"] = dato.unidad
            if dato.descripcion and not es_pieza:
                datos["descripcion"] = dato.descripcion
            inventario.items.append(InventarioItem(
                **datos,
                lote=lote,
                etapa="MATERIAL",
                operacion=lote,
                titulo_operacion=titulo_lote_material(
                    lote,
                    dato.descripcion,
                ),
                stock_sistema=float(dato.cantidad),
                stock_pendiente=False,
            ))

    return {
        "codigos_material": len(grupos),
        "lotes_mp": sum(
            len(reporte_mp.mp.get(codigo, {}))
            for codigo in grupos
        ),
        "sin_registro_mp": sorted(set(faltantes_mp) - {""}),
    }


@router.post("/inventarios/{inventario_id}/actualizar-stock-excel")
async def actualizar_stock_inventario_excel(
    inventario_id: int,
    conteos_json: str = Form(...),
    archivo_pt: UploadFile | None = File(default=None),
    archivo_prd: UploadFile | None = File(default=None),
    archivo_mp: UploadFile | None = File(default=None),
    archivo_asignado: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado == "Cerrado":
        raise HTTPException(
            status_code=409,
            detail="El stock de un inventario cerrado no puede modificarse",
        )
    try:
        entrada = ConteoEntrada.model_validate_json(conteos_json)
    except Exception as error:
        raise HTTPException(
            status_code=422,
            detail="Los conteos enviados no son válidos",
        ) from error
    aplicar_conteos_recibidos(inventario, entrada, db)

    async def leer(archivo, tipo):
        if archivo is None:
            return None
        try:
            contenido = await archivo.read()
            if len(contenido) > 20 * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail=f"El reporte {tipo} supera el límite de 20 MB",
                )
            return leer_reporte_stock(contenido, tipo)
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

    reporte_pt = await leer(archivo_pt, "PT")
    reporte_prd = await leer(archivo_prd, "PRD")
    reporte_mp = await leer(archivo_mp, "MP")
    reporte_asignado = await leer(archivo_asignado, "ASIGNADO")

    tiene_pt = any(item.etapa == "TERMINADO" for item in inventario.items)
    tiene_prd = any(
        item.etapa in {"OPERACION", "PROCESO_GLOBAL"}
        for item in inventario.items
    )
    tiene_mp = any(item.etapa == "MATERIAL" for item in inventario.items)
    validar_reporte_necesario(reporte_pt, tiene_pt, "PT")
    validar_reporte_necesario(reporte_prd, tiene_prd, "PRD")
    validar_reporte_necesario(reporte_mp, tiene_mp, "MP")

    resumen = actualizar_piezas_desde_excel(
        inventario,
        reporte_pt,
        reporte_prd,
        reporte_asignado,
    )
    if reporte_mp:
        resumen.update(
            actualizar_materiales_desde_excel(inventario, reporte_mp)
        )
    if (
        inventario.estado == "En preparación"
        and any(item.conteo_fisico is not None for item in inventario.items)
    ):
        inventario.estado = "En conteo"
    inventario.stock_actualizado_en = datetime.now()
    inventario.stock_origen = "EXCEL"
    db.commit()
    sincronizar_bases(
        inventario.id,
        {item.id: item.conteo_fisico for item in inventario.items},
    )
    return {
        "inventario": inventario_dict(buscar_inventario(db, inventario.id)),
        "resumen": resumen,
    }


@router.put("/inventarios/{inventario_id}/conteo")
def guardar_conteo(
    inventario_id: int,
    entrada: ConteoEntrada,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado == "Cerrado":
        raise HTTPException(
            status_code=409,
            detail="El inventario está cerrado y no puede modificarse",
        )

    aplicar_conteos_recibidos(inventario, entrada, db)

    inventario.estado = "En conteo"
    db.commit()
    sincronizar_bases(
        inventario.id,
        {item.id: item.conteo_fisico for item in inventario.items},
    )
    db.refresh(inventario)
    return inventario_dict(inventario)


@router.get("/inventarios/{inventario_id}/conteo-movil")
def obtener_conteo_movil(
    inventario_id: int,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.modalidad_conteo == "MEDIOS":
        return {"inventario": inventario_dict(inventario), "cajas": []}
    cajas = listar_cajas(inventario_id)
    total_por_item: dict[int, float] = {}
    cantidad_por_item: dict[int, int] = {}
    for caja in cajas:
        item_id = int(caja["item_id"])
        total_por_item[item_id] = (
            total_por_item.get(item_id, 0) + float(caja["cantidad"])
        )
        cantidad_por_item[item_id] = (
            cantidad_por_item.get(item_id, 0) + 1
        )
    datos = inventario_dict(inventario)
    for item in datos["items"]:
        item_id = item["id"]
        item["total_cajas"] = total_por_item.get(item_id, 0)
        item["cantidad_cajas"] = cantidad_por_item.get(item_id, 0)
    return {
        "inventario": datos,
        "cajas": cajas[:250],
    }


@router.put("/inventarios/{inventario_id}/conteo-movil/medios/{item_id}")
def guardar_medio_movil(
    inventario_id: int,
    item_id: int,
    entrada: ConteoMedioMovilEntrada,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado == "Cerrado":
        raise HTTPException(status_code=409, detail="El inventario está cerrado")
    if inventario.modalidad_conteo != "MEDIOS":
        raise HTTPException(status_code=409, detail="Este inventario no es de medios")
    item = db.scalar(
        select(InventarioItem)
        .where(InventarioItem.id == item_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if item is None or item.inventario_id != inventario_id:
        raise HTTPException(status_code=404, detail="No se encontró el medio")
    item.conteo_vacios = entrada.conteo_vacios
    item.conteo_llenos = entrada.conteo_llenos
    item.conteo_rotos = entrada.conteo_rotos
    item.conteo_fisico = (
        entrada.conteo_vacios + entrada.conteo_llenos + entrada.conteo_rotos
    )
    inventario.estado = "En conteo"
    db.commit()
    sincronizar_bases(inventario_id, {item.id: item.conteo_fisico})
    return inventario_dict(buscar_inventario(db, inventario_id))


@router.post("/inventarios/{inventario_id}/conteo-movil/cajas")
def registrar_cajas_movil(
    inventario_id: int,
    entrada: ConteoCajasEntrada,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado == "Cerrado":
        raise HTTPException(
            status_code=409,
            detail="El inventario está cerrado y no puede modificarse",
        )
    if inventario.modalidad_conteo == "MEDIOS":
        raise HTTPException(
            status_code=409,
            detail="Este inventario no admite conteo móvil por registros",
        )

    items_validos = {item.id for item in inventario.items}
    resultados = []
    for caja_entrada in entrada.cajas:
        if caja_entrada.item_id not in items_validos:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El ítem {caja_entrada.item_id} no pertenece al "
                    "inventario"
                ),
            )
        item = db.scalar(
            select(InventarioItem)
            .where(InventarioItem.id == caja_entrada.item_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if item is None or item.inventario_id != inventario_id:
            raise HTTPException(status_code=404, detail="Renglón no encontrado")
        capturado_en = caja_entrada.capturado_en or datetime.now()
        if capturado_en.tzinfo is not None:
            capturado_en = capturado_en.replace(tzinfo=None)
        try:
            registro = registrar_caja(
                cliente_uid=caja_entrada.cliente_uid,
                inventario_id=inventario_id,
                item_id=item.id,
                cantidad=float(caja_entrada.cantidad),
                observacion=caja_entrada.observacion.strip(),
                dispositivo=caja_entrada.dispositivo.strip(),
                capturado_en=capturado_en,
                conteo_actual=float(item.conteo_fisico or 0),
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        item.conteo_fisico = registro["conteo_fisico"]
        resultados.append({
            **registro["caja"],
            "duplicada": registro["duplicada"],
        })

    inventario.estado = "En conteo"
    db.commit()
    return {
        "cajas": resultados,
        "inventario": inventario_dict(buscar_inventario(db, inventario_id)),
    }


@router.get("/inventarios/{inventario_id}/conteo-movil/cajas/{item_id}")
def obtener_cajas_item_movil(
    inventario_id: int,
    item_id: int,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    item = next((item for item in inventario.items if item.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Renglón no encontrado")
    cajas = [
        caja for caja in listar_cajas(inventario_id)
        if int(caja["item_id"]) == item_id
    ]
    total_registros = sum(float(caja["cantidad"]) for caja in cajas)
    conteo_fisico = None if item.conteo_fisico is None else float(item.conteo_fisico)
    return {
        "item_id": item_id,
        "conteo_fisico": conteo_fisico,
        "cantidad_registros": len(cajas),
        "total_registros": total_registros,
        "conteo_base": None if conteo_fisico is None else conteo_fisico - total_registros,
        "cajas": cajas,
    }


@router.post("/inventarios/{inventario_id}/conteo-movil/cajas/eliminar")
def eliminar_cajas_movil(
    inventario_id: int,
    entrada: EliminarCajasMovilEntrada,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado == "Cerrado":
        raise HTTPException(status_code=409, detail="El inventario está cerrado")
    resultado = eliminar_cajas(inventario_id, set(entrada.caja_ids))
    items = {item.id: item for item in inventario.items}
    for item_id, conteo in resultado["conteos"].items():
        item = items.get(int(item_id))
        if item is not None:
            item.conteo_fisico = conteo
    db.commit()
    return {
        "eliminadas": [caja["id"] for caja in resultado["cajas"]],
        "conteos": resultado["conteos"],
    }


@router.delete("/inventarios/{inventario_id}/conteo-movil/cajas/{caja_id}")
def eliminar_caja_movil(
    inventario_id: int,
    caja_id: int,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado == "Cerrado":
        raise HTTPException(
            status_code=409,
            detail="El inventario está cerrado y no puede modificarse",
        )
    registro = eliminar_caja(inventario_id, caja_id)
    if registro is None:
        return {"eliminada": False, "caja_id": caja_id}
    item = db.scalar(
        select(InventarioItem)
        .where(InventarioItem.id == registro["caja"]["item_id"])
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Renglón no encontrado")
    item.conteo_fisico = registro["conteo_fisico"]
    db.commit()
    return {
        "eliminada": True,
        "item_id": item.id,
        "conteo_fisico": item.conteo_fisico,
        "inventario": inventario_dict(buscar_inventario(db, inventario_id)),
    }


@router.put("/inventarios/{inventario_id}/datos")
def guardar_datos_inventario(
    inventario_id: int,
    entrada: InventarioDatosEntrada,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    inventario.ambito = entrada.ambito
    inventario.mes_cierre = primer_dia_mes(entrada.mes_cierre)
    inventario.observaciones = entrada.observaciones.strip()
    db.commit()
    db.refresh(inventario)
    guardar_mes_inventario(inventario.id, entrada.mes_cierre)
    return inventario_dict(inventario)


@router.post("/inventarios/{inventario_id}/articulos", status_code=201)
def agregar_articulo_inventario(
    inventario_id: int,
    entrada: AgregarArticuloInventarioEntrada,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado == "Cerrado":
        raise HTTPException(
            status_code=409,
            detail="No se pueden agregar artículos a un inventario cerrado",
        )

    codigo = normalizar_codigo(entrada.codigo)
    # Los inventarios de piezas también pueden incorporar una MP encontrada
    # durante el recorrido. La búsqueda sigue validándose contra mtprim01.
    if (
        inventario.categoria == "MATERIA_PRIMA"
        and entrada.tipo_articulo != "MATERIA_PRIMA"
    ):
        raise HTTPException(
            status_code=422,
            detail="Este inventario admite materias primas",
        )
    if (
        inventario.modalidad_conteo == "MEDIOS"
        and entrada.tipo_articulo != "PIEZA"
    ):
        raise HTTPException(
            status_code=422,
            detail="Un inventario de medios sólo admite piezas terminadas",
        )

    if entrada.tipo_articulo == "PIEZA":
        repetido = any(
            item.codigo == codigo
            and item.etapa in {
                "OPERACION",
                "PROCESO_GLOBAL",
                "TERMINADO",
            }
            for item in inventario.items
        )
    else:
        repetido = any(
            item.etapa == "MATERIAL"
            and normalizar_codigo(item.codigo_material or item.codigo) == codigo
            for item in inventario.items
        )
    if repetido:
        raise HTTPException(
            status_code=409,
            detail=f"El código {codigo} ya forma parte del inventario",
        )

    articulo_entrada = ArticuloInventarioEntrada(
        codigo=codigo,
        tipo_articulo=entrada.tipo_articulo,
        contar_material=entrada.contar_material,
    )
    _articulo, nuevos_items = construir_items_articulo(
        articulo_entrada,
        tipo_conteo=entrada.tipo_conteo,
        modalidad_conteo=inventario.modalidad_conteo,
    )
    if inventario.categoria == "CICLICO":
        for item in nuevos_items:
            item.ruta = codigo
            item.nivel = 0

    if entrada.tipo_articulo == "PIEZA":
        materiales_existentes = {
            normalizar_codigo(item.codigo_material or item.codigo)
            for item in inventario.items
            if item.etapa == "MATERIAL"
        }
        nuevos_items = [
            item for item in nuevos_items
            if not (
                item.etapa == "MATERIAL"
                and normalizar_codigo(item.codigo_material)
                in materiales_existentes
            )
        ]

    inventario.items.extend(nuevos_items)
    fuente_nueva = fuente_stock_actual()
    inventario.stock_origen = (
        fuente_nueva
        if inventario.stock_origen in {"", fuente_nueva}
        else "MIXTO"
    )
    inventario.stock_actualizado_en = datetime.now()
    db.commit()
    return inventario_dict(buscar_inventario(db, inventario.id))


@router.post(
    "/inventarios/{inventario_id}/materiales/{codigo}/lotes",
    status_code=201,
)
def agregar_lote_material_inventario(
    inventario_id: int,
    codigo: str,
    entrada: AgregarLoteMaterialEntrada,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado == "Cerrado":
        raise HTTPException(
            status_code=409,
            detail="No se pueden agregar lotes a un inventario cerrado",
        )
    codigo = normalizar_codigo(codigo)
    codigo_pieza = normalizar_codigo(entrada.codigo_pieza)
    lote = entrada.lote.strip()
    material = buscar_material(codigo)
    if material is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontró el código de materia prima",
        )
    candidatas = [
        item for item in inventario.items
        if item.etapa == "MATERIAL"
        and normalizar_codigo(item.codigo_material or item.codigo) == codigo
    ]
    propietarios = {normalizar_codigo(item.codigo) for item in candidatas}
    if not codigo_pieza:
        if len(propietarios) == 1:
            codigo_pieza = next(iter(propietarios))
        elif inventario.categoria == "MATERIA_PRIMA":
            codigo_pieza = codigo
        else:
            raise HTTPException(
                status_code=422,
                detail="Indicá para qué pieza querés agregar el lote",
            )
    filas_material = [
        item for item in candidatas
        if normalizar_codigo(item.codigo) == codigo_pieza
    ]
    if not filas_material:
        raise HTTPException(
            status_code=404,
            detail=(
                f"La MP {codigo} no forma parte de la pieza {codigo_pieza} "
                "en este inventario"
            ),
        )
    repetido = next(
        (
            item for item in filas_material if item.lote == lote
        ),
        None,
    )
    if repetido is not None:
        raise HTTPException(
            status_code=409,
            detail=f"El lote {lote} ya está incluido para {codigo}",
        )

    stock_lote = float(next(
        (item.stock for item in material.lotes if item.lote == lote),
        0,
    ))
    marcador = next(
        (
            item for item in filas_material
            if not item.lote and item.conteo_fisico is None
        ),
        None,
    )
    if marcador is not None:
        marcador.lote = lote
        marcador.operacion = lote
        marcador.titulo_operacion = titulo_lote_material(
            lote,
            material.descripcion,
        )
        marcador.stock_sistema = stock_lote
        marcador.unidad = material.unidad
    else:
        base = filas_material[0]
        datos = datos_base_item(base)
        datos["unidad"] = material.unidad or datos.get("unidad", "")
        inventario.items.append(InventarioItem(
            **datos,
            lote=lote,
            etapa="MATERIAL",
            operacion=lote,
            titulo_operacion=titulo_lote_material(
                lote,
                material.descripcion,
            ),
            stock_sistema=stock_lote,
        ))
    inventario.stock_actualizado_en = datetime.now()
    db.commit()
    return inventario_dict(buscar_inventario(db, inventario.id))


@router.delete("/inventarios/{inventario_id}/lotes/{item_id}")
def eliminar_lote_material_inventario(
    inventario_id: int,
    item_id: int,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado == "Cerrado":
        raise HTTPException(
            status_code=409,
            detail="No se pueden eliminar lotes de un inventario cerrado",
        )
    item = next((fila for fila in inventario.items if fila.id == item_id), None)
    if item is None or item.etapa != "MATERIAL" or not item.lote:
        raise HTTPException(status_code=404, detail="No se encontró el lote")
    tiene_registros = any(
        int(caja["item_id"]) == item.id
        for caja in listar_cajas(inventario_id)
    )
    if item.conteo_fisico is not None or tiene_registros:
        raise HTTPException(
            status_code=409,
            detail=(
                "El lote ya tiene registros. Eliminá primero sus registros "
                "de conteo y volvé a intentarlo."
            ),
        )

    codigo = normalizar_codigo(item.codigo_material or item.codigo)
    otras_filas = [
        fila for fila in inventario.items
        if fila.id != item.id
        and fila.codigo == item.codigo
        and fila.etapa == "MATERIAL"
        and normalizar_codigo(fila.codigo_material or fila.codigo) == codigo
    ]
    if otras_filas:
        db.delete(item)
        eliminar_conteo_local_items(inventario_id, {item.id})
    else:
        # Conserva el material dentro del inventario para poder cargar enseguida
        # el lote correcto.
        item.lote = ""
        item.operacion = ""
        item.titulo_operacion = "Sin lote cargado"
        item.stock_sistema = 0
    inventario.stock_actualizado_en = datetime.now()
    db.commit()
    return inventario_dict(buscar_inventario(db, inventario.id))


@router.post("/inventarios/{inventario_id}/eliminar-filas")
def eliminar_filas_inventario(
    inventario_id: int,
    entrada: EliminarFilasInventarioEntrada,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado == "Cerrado":
        raise HTTPException(
            status_code=409,
            detail="El inventario está cerrado y no puede modificarse",
        )

    ids_solicitados = set(entrada.item_ids)
    items_encontrados = [
        item for item in inventario.items if item.id in ids_solicitados
    ]
    if len(items_encontrados) != len(ids_solicitados):
        raise HTTPException(
            status_code=404,
            detail="Uno o más renglones no pertenecen a este inventario",
        )
    if len(items_encontrados) >= len(inventario.items):
        raise HTTPException(
            status_code=409,
            detail=(
                "El inventario no puede quedar vacío. "
                "Si no lo vas a usar, eliminá el inventario completo."
            ),
        )

    for item in items_encontrados:
        db.delete(item)
    db.commit()
    eliminar_conteo_local_items(inventario_id, ids_solicitados)
    inventario = buscar_inventario(db, inventario_id)
    return inventario_dict(inventario)


@router.post("/inventarios/{inventario_id}/eliminar-codigo-movil")
def eliminar_codigo_movil(
    inventario_id: int,
    entrada: EliminarFilasInventarioEntrada,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado == "Cerrado":
        raise HTTPException(
            status_code=409,
            detail="El inventario está cerrado y no puede modificarse",
        )
    ids_solicitados = set(entrada.item_ids)
    items = [item for item in inventario.items if item.id in ids_solicitados]
    if not ids_solicitados or len(items) != len(ids_solicitados):
        raise HTTPException(
            status_code=404,
            detail="Uno o más renglones no pertenecen a este inventario",
        )
    codigos = {normalizar_codigo(item.codigo) for item in items}
    if len(codigos) != 1:
        raise HTTPException(
            status_code=422,
            detail="La eliminación móvil debe corresponder a un único código",
        )
    ids_codigo = {
        item.id for item in inventario.items
        if normalizar_codigo(item.codigo) in codigos
    }
    if ids_codigo != ids_solicitados:
        raise HTTPException(
            status_code=409,
            detail="Actualizá la pantalla antes de eliminar este código",
        )
    cajas = listar_cajas(inventario_id)
    if any(int(caja["item_id"]) in ids_codigo for caja in cajas) or any(
        item.conteo_fisico is not None for item in items
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "El código tiene registros. Eliminalos primero y volvé a "
                "intentarlo."
            ),
        )
    if len(items) >= len(inventario.items):
        raise HTTPException(
            status_code=409,
            detail="El inventario no puede quedar vacío",
        )
    for item in items:
        db.delete(item)
    db.commit()
    eliminar_conteo_local_items(inventario_id, ids_codigo)
    return inventario_dict(buscar_inventario(db, inventario_id))


@router.post("/inventarios/{inventario_id}/cerrar")
def cerrar_inventario(
    inventario_id: int,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if any(item.conteo_fisico is None for item in inventario.items):
        raise HTTPException(
            status_code=409,
            detail="No se puede cerrar: todavía hay artículos sin contar",
        )

    inventario.estado = "Cerrado"
    inventario.cerrado_en = datetime.now()
    db.commit()
    db.refresh(inventario)
    return inventario_dict(inventario)


@router.post("/inventarios/{inventario_id}/reabrir")
def reabrir_inventario(
    inventario_id: int,
    entrada: ReabrirInventarioEntrada,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado != "Cerrado":
        raise HTTPException(status_code=409, detail="El inventario ya está habilitado")
    clave_configurada = settings.INVENTORY_ADMIN_PASSWORD
    if not clave_configurada:
        raise HTTPException(
            status_code=503,
            detail=(
                "Configurá INVENTORY_ADMIN_PASSWORD en el archivo .env "
                "y reiniciá el servidor."
            ),
        )
    if not hmac.compare_digest(entrada.clave, clave_configurada):
        raise HTTPException(status_code=403, detail="La clave administrativa es incorrecta")

    autorizado = entrada.autorizado_por.strip()
    motivo = entrada.motivo.strip()
    momento = datetime.now().strftime("%d/%m/%Y %H:%M")
    registro = f"[REAPERTURA {momento} · Autorizó: {autorizado} · Motivo: {motivo}]"
    observacion_anterior = (inventario.observaciones or "").strip()
    espacio_anterior = max(0, 4000 - len(registro) - 2)
    inventario.observaciones = (
        f"{observacion_anterior[:espacio_anterior]}\n{registro}".strip()
    )
    inventario.estado = "En conteo"
    inventario.cerrado_en = None
    db.commit()
    return inventario_dict(buscar_inventario(db, inventario_id))


def stock_actual_para_item(item: InventarioItem) -> float:
    if item.etapa == "MATERIAL":
        material = buscar_material(item.codigo_material or item.codigo)
        if material is None:
            return float(item.stock_sistema)
        if item.lote:
            return float(next((x.stock for x in material.lotes if x.lote == item.lote), 0))
        return float(material.stock_total)
    pieza = buscar_pieza(item.codigo)
    if pieza is None:
        return float(item.stock_sistema)
    if item.etapa == "TERMINADO":
        return float(pieza.stock_terminado) + float(item.stock_asignado or 0)
    if item.etapa == "PROCESO_GLOBAL":
        return float(pieza.stock_proceso_total)
    if item.etapa == "OPERACION":
        return float(next((x.stock for x in pieza.operaciones if x.operacion == item.operacion), 0))
    return float(item.stock_sistema)


@router.post("/inventarios/{inventario_id}/reconteos")
def crear_reconteo(
    inventario_id: int,
    entrada: ReconteoCrearEntrada,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    if inventario.estado != "Cerrado":
        raise HTTPException(status_code=409, detail="Sólo se puede recontar un inventario cerrado")
    ids = set(entrada.item_ids)
    seleccionados = [x for x in inventario.items if x.id in ids]
    if len(seleccionados) != len(ids):
        raise HTTPException(status_code=404, detail="Hay renglones que no pertenecen al inventario")
    if entrada.tipo == "COMPLETO" and len(seleccionados) != len(inventario.items):
        raise HTTPException(status_code=400, detail="El reconteo completo debe incluir todos los renglones")

    hoy = date.today()
    ultimo_id = db.scalar(select(func.max(Inventario.id))) or 0
    nuevo = Inventario(
        codigo=f"INV-{hoy.year}-{ultimo_id + 12:03d}",
        origen="RECONTEO",
        cliente=inventario.cliente,
        plantilla_id=inventario.plantilla_id,
        fecha=hoy,
        mes_cierre=primer_dia_mes(hoy),
        responsable=(entrada.responsable or inventario.responsable).strip(),
        colaboradores=inventario.colaboradores,
        ambito=inventario.ambito,
        estado="En preparación",
        categoria=inventario.categoria,
        tipo_inventario_codigo=inventario.tipo_inventario_codigo,
        modalidad_conteo=inventario.modalidad_conteo,
        formato_impresion=inventario.formato_impresion,
        formato_version_id=inventario.formato_version_id,
        controla_remitos=inventario.controla_remitos,
        observaciones=entrada.observaciones.strip(),
        stock_actualizado_en=(
            datetime.now() if entrada.stock_referencia == "ACTUALIZADO"
            else inventario.stock_actualizado_en
        ),
        stock_origen=(
            fuente_stock_actual() if entrada.stock_referencia == "ACTUALIZADO"
            else inventario.stock_origen
        ),
    )
    campos_copiados = (
        "codigo", "codigo_cliente", "codigo_material", "descripcion",
        "ubicacion", "diametro", "largo", "espesor", "unidad", "lote",
        "codigo_padre", "nivel", "uso", "ruta", "tipo_estructura",
        "etapa", "operacion", "titulo_operacion", "proveedor",
        "stock_pendiente", "stock_asignado", "contar_material",
    )
    nuevo.items = []
    for original in seleccionados:
        datos = {campo: getattr(original, campo) for campo in campos_copiados}
        datos["stock_sistema"] = (
            stock_actual_para_item(original)
            if entrada.stock_referencia == "ACTUALIZADO"
            else float(original.stock_sistema)
        )
        nuevo.items.append(InventarioItem(**datos))

    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    guardar_mes_inventario(nuevo.id, hoy)
    try:
        crear_relacion(
            inventario.id, nuevo.id, entrada.tipo, entrada.stock_referencia,
        )
    except Exception:
        db.delete(nuevo)
        db.commit()
        eliminar_mes_inventario(nuevo.id)
        raise
    return inventario_dict(buscar_inventario(db, nuevo.id))


@router.delete("/inventarios/{inventario_id}", status_code=204)
def eliminar_inventario(
    inventario_id: int,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    db.delete(inventario)
    db.commit()
    eliminar_relaciones_inventario(inventario_id)
    eliminar_conteo_local_inventario(inventario_id)
    eliminar_mes_inventario(inventario_id)
    return Response(status_code=204)


@router.get("/inventarios/{inventario_id}/excel")
def descargar_excel(
    inventario_id: int,
    db: Session = Depends(get_db),
):
    inventario = buscar_inventario(db, inventario_id)
    archivo = generar_excel(inventario, listar_cajas(inventario_id))
    nombre = f"{inventario.codigo}.xlsx"
    return StreamingResponse(
        archivo,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
        },
    )
