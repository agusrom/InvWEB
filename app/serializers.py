from datetime import date

from app.models import (
    Inventario,
    Plantilla,
    ProgramacionInventario,
)
from app.local_count_store import obtener_revision
from app.inventory_aux_store import (
    plantillas_inventario,
    tipos_items_plantilla,
)
from app.local_recount_store import relaciones_de_inventario
from app.services.indicator_settings import configuracion_actual


def metricas_conteo_item(
    item,
    tolerancia_pct: float | None = None,
) -> dict:
    """Calcula diferencia y porcentajes de un renglón ya contado."""
    if item.conteo_fisico is None or item.stock_pendiente:
        return {
            "diferencia": None,
            "relacion_porcentaje": None,
            "desvio_porcentaje": None,
            "dentro_tolerancia": None,
        }

    fisico = float(item.conteo_fisico)
    teorico = float(item.stock_sistema)
    diferencia = fisico - teorico
    if tolerancia_pct is None:
        tolerancia_pct = float(
            configuracion_actual()["tolerancia_pct"]
        )

    if teorico == 0:
        if fisico == 0:
            relacion = 100.0
            desvio = 0.0
            dentro_tolerancia = True
        else:
            relacion = 200.0
            desvio = 100.0
            dentro_tolerancia = False
    else:
        relacion = fisico * 100 / teorico
        desvio = diferencia * 100 / teorico
        dentro_tolerancia = abs(desvio) <= (tolerancia_pct + 1e-9)

    return {
        "diferencia": diferencia,
        "relacion_porcentaje": relacion,
        "desvio_porcentaje": desvio,
        "dentro_tolerancia": dentro_tolerancia,
    }


def metricas_confiabilidad(inventario: Inventario) -> dict:
    evaluables = [
        item for item in inventario.items if not item.stock_pendiente
    ]
    metricas = [metricas_conteo_item(item) for item in evaluables]
    evaluados = sum(
        metrica["dentro_tolerancia"] is not None for metrica in metricas
    )
    correctos = sum(
        metrica["dentro_tolerancia"] is True for metrica in metricas
    )
    total = len(evaluables)
    return {
        "items_ok": correctos,
        "items_evaluados": evaluados,
        "items_evaluables": total,
        "confiabilidad": correctos * 100 / total if total else None,
        "confiabilidad_completa": bool(total) and evaluados == total,
    }


def plantilla_dict(plantilla: Plantilla) -> dict:
    tipos = tipos_items_plantilla(plantilla.id)
    return {
        "id": plantilla.id,
        "nombre": plantilla.nombre,
        "cliente": plantilla.cliente,
        "descripcion": plantilla.descripcion,
        "categoria": plantilla.categoria,
        "tipo_inventario_codigo": plantilla.tipo_inventario_codigo,
        "tipo_conteo": plantilla.tipo_conteo,
        "formato_impresion": plantilla.formato_impresion,
        "controla_remitos": plantilla.controla_remitos,
        "activa": plantilla.activa,
        "creada_en": plantilla.creada_en.isoformat(timespec="seconds"),
        "actualizada_en": (
            (plantilla.actualizada_en or plantilla.creada_en)
            .isoformat(timespec="seconds")
        ),
        "items": [
            {
                "id": item.id,
                "codigo": item.codigo,
                "tipo_articulo": tipos.get(
                    item.codigo.strip().upper(),
                    "MATERIA_PRIMA"
                    if plantilla.categoria == "MATERIA_PRIMA"
                    else "PIEZA",
                ),
                "codigo_cliente": item.codigo_cliente,
                "codigo_material": item.codigo_material,
                "descripcion": item.descripcion,
                "ubicacion": item.ubicacion,
                "diametro": item.diametro,
                "largo": item.largo,
                "espesor": item.espesor,
                "unidad": item.unidad,
                "stock_referencia": item.stock_referencia,
                "contar_material": item.contar_material,
                "tipo_estructura": item.tipo_estructura,
            }
            for item in plantilla.items
        ],
    }


def inventario_dict(inventario: Inventario) -> dict:
    items_contados = sum(
        item.conteo_fisico is not None for item in inventario.items
    )
    total_items = len(inventario.items)
    progreso = round(items_contados * 100 / total_items) if total_items else 0
    confiabilidad = metricas_confiabilidad(inventario)

    relaciones = relaciones_de_inventario(inventario.id)

    return {
        "id": inventario.id,
        "codigo": inventario.codigo,
        "origen": inventario.origen,
        "cliente": inventario.cliente,
        "plantilla_id": inventario.plantilla_id,
        "plantillas_origen": plantillas_inventario(inventario.id),
        "programacion_id": inventario.programacion_id,
        "fecha_programada": (
            inventario.fecha_programada.isoformat()
            if inventario.fecha_programada
            else None
        ),
        "mes_cierre": (
            inventario.mes_cierre.isoformat()
            if inventario.mes_cierre
            else None
        ),
        "fecha": inventario.fecha.isoformat(),
        "responsable": inventario.responsable,
        "colaboradores": inventario.colaboradores,
        "ambito": inventario.ambito,
        "estado": inventario.estado,
        "categoria": inventario.categoria,
        "tipo_inventario_codigo": inventario.tipo_inventario_codigo,
        "modalidad_conteo": inventario.modalidad_conteo,
        "formato_impresion": inventario.formato_impresion,
        "controla_remitos": inventario.controla_remitos,
        "ultimo_remito_ingreso": inventario.ultimo_remito_ingreso,
        "ultimo_remito_egreso": inventario.ultimo_remito_egreso,
        "observaciones": inventario.observaciones,
        "stock_actualizado_en": (
            inventario.stock_actualizado_en.isoformat(timespec="seconds")
            if inventario.stock_actualizado_en
            else None
        ),
        "stock_origen": inventario.stock_origen,
        "conteo_modificado_en": obtener_revision(inventario.id),
        "cerrado_en": (
            inventario.cerrado_en.isoformat(timespec="seconds")
            if inventario.cerrado_en
            else None
        ),
        "progreso": progreso,
        **confiabilidad,
        "items": items_inventario_dict(inventario),
        "relacion_reconteo": relaciones["origen"],
        "reconteos_vinculados": relaciones["reconteos"],
    }


def programacion_dict(programacion: ProgramacionInventario, ejecuciones: int | None = None) -> dict:
    hoy = date.today()
    if not programacion.activa:
        estado = (
            "Completada"
            if programacion.frecuencia == "UNA_VEZ"
            and programacion.ultima_ejecucion
            else "Pausada"
        )
    elif programacion.fecha_proxima < hoy:
        estado = "Vencida"
    elif programacion.fecha_proxima == hoy:
        estado = "Para hoy"
    else:
        estado = "Próxima"

    return {
        "id": programacion.id,
        "plantilla_id": programacion.plantilla_id,
        "plantilla_nombre": programacion.plantilla.nombre,
        "cliente": programacion.plantilla.cliente,
        "categoria": programacion.plantilla.categoria,
        "tipo_inventario_codigo": (
            programacion.plantilla.tipo_inventario_codigo
        ),
        "fecha_proxima": programacion.fecha_proxima.isoformat(),
        "mes_cierre_proximo": (
            programacion.mes_cierre_proximo.isoformat()
            if programacion.mes_cierre_proximo
            else None
        ),
        "frecuencia": programacion.frecuencia,
        "dia_mes": programacion.dia_mes,
        "responsable": programacion.responsable,
        "colaboradores": programacion.colaboradores,
        "observaciones": programacion.observaciones,
        "activa": programacion.activa,
        "estado": estado,
        "ultima_ejecucion": (
            programacion.ultima_ejecucion.isoformat()
            if programacion.ultima_ejecucion
            else None
        ),
        "ejecuciones": len(programacion.inventarios) if ejecuciones is None else ejecuciones,
    }


def items_inventario_dict(inventario):
    """Renglones sin consultas de relaciones, revisión ni cierres del inventario."""
    return [
        {
            "id": item.id,
            "codigo": item.codigo,
            "codigo_cliente": item.codigo_cliente,
            "codigo_material": item.codigo_material,
            "descripcion": item.descripcion,
            "ubicacion": item.ubicacion,
            "diametro": item.diametro,
            "largo": item.largo,
            "espesor": item.espesor,
            "unidad": item.unidad,
            "lote": item.lote,
            "codigo_padre": item.codigo_padre,
            "nivel": item.nivel,
            "uso": item.uso,
            "ruta": item.ruta,
            "tipo_estructura": item.tipo_estructura,
            "etapa": item.etapa,
            "operacion": item.operacion,
            "titulo_operacion": item.titulo_operacion,
            "proveedor": item.proveedor,
            "stock_pendiente": item.stock_pendiente,
            "stock_sistema": item.stock_sistema,
            "stock_asignado": item.stock_asignado,
            "conteo_fisico": item.conteo_fisico,
            "conteo_vacios": item.conteo_vacios,
            "conteo_llenos": item.conteo_llenos,
            "conteo_rotos": item.conteo_rotos,
            "medios_utilizables": item.conteo_vacios,
            "contar_material": item.contar_material,
            "causa_diferencia_codigo": item.causa_diferencia_codigo,
            "ajustado_sistema": item.ajustado_sistema,
            "ajustado_sistema_en": (
                item.ajustado_sistema_en.isoformat()
                if item.ajustado_sistema_en
                else None
            ),
            "observaciones": item.observaciones,
            **metricas_conteo_item(item),
        }
        for item in inventario.items
    ]
