from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from app.serializers import metricas_conteo_item


def fecha_inventario(inventario) -> date:
    if inventario.cerrado_en:
        return inventario.cerrado_en.date()
    return inventario.fecha


def inventario_mensual(inventario) -> bool:
    programacion = getattr(inventario, "programacion", None)
    return (
        programacion is not None
        and str(getattr(programacion, "frecuencia", "") or "").upper()
        == "MENSUAL"
    )


def fecha_cierre_reporte(inventario) -> date:
    """Mes contable explícito; conserva compatibilidad con datos históricos."""
    mes_cierre = getattr(inventario, "mes_cierre", None)
    if mes_cierre is not None:
        return date(mes_cierre.year, mes_cierre.month, 1)
    return date(
        fecha_inventario(inventario).year,
        fecha_inventario(inventario).month,
        1,
    )


def limites_mes(mes_cierre: str) -> tuple[date, date]:
    anio, mes = (int(parte) for parte in mes_cierre.split("-", 1))
    inicio = date(anio, mes, 1)
    if mes == 12:
        siguiente = date(anio + 1, 1, 1)
    else:
        siguiente = date(anio, mes + 1, 1)
    return inicio, siguiente - timedelta(days=1)


def mes_anterior(fecha: date) -> date:
    if fecha.month == 1:
        return date(fecha.year - 1, 12, 1)
    return date(fecha.year, fecha.month - 1, 1)


def porcentaje(parte: int, total: int) -> float | None:
    return parte * 100 / total if total else None


def inventario_programado(inventario) -> bool:
    """Reconoce también programaciones históricas sin relación conservada."""
    return (
        getattr(inventario, "programacion_id", None) is not None
        or getattr(inventario, "fecha_programada", None) is not None
    )


def tipo_contenido_inventario(inventario) -> str:
    """Clasifica por contenido, independientemente del modo de creación."""
    modalidad = str(
        getattr(inventario, "modalidad_conteo", "") or ""
    ).upper()
    categoria = str(getattr(inventario, "categoria", "") or "").upper()
    tipo_codigo = str(
        getattr(inventario, "tipo_inventario_codigo", "") or ""
    ).upper()
    if modalidad == "MEDIOS" or tipo_codigo == "MEDIOS":
        return "medios"
    if categoria == "MATERIA_PRIMA" or tipo_codigo == "MATERIA_PRIMA":
        return "materia_prima"
    return "piezas"


def resumen_items(inventarios: list) -> dict:
    items = [
        item
        for inventario in inventarios
        for item in inventario.items
        if not item.stock_pendiente
    ]
    evaluados = []
    for item in items:
        metrica = metricas_conteo_item(item)
        if metrica["dentro_tolerancia"] is not None:
            evaluados.append((item, metrica))
    correctos = sum(
        metrica["dentro_tolerancia"] is True
        for _item, metrica in evaluados
    )
    diferencias = [
        (item, metrica)
        for item, metrica in evaluados
        if metrica["dentro_tolerancia"] is False
    ]
    ajustados = sum(item.ajustado_sistema for item, _metrica in diferencias)
    con_causa = sum(
        bool(item.causa_diferencia_codigo)
        for item, _metrica in diferencias
    )
    return {
        "evaluados": len(evaluados),
        "correctos": correctos,
        "confiabilidad": porcentaje(correctos, len(evaluados)),
        "diferencias": len(diferencias),
        "porcentaje_diferencias": porcentaje(
            len(diferencias),
            len(evaluados),
        ),
        "ajustados": ajustados,
        "ajustes_pendientes": len(diferencias) - ajustados,
        "con_causa": con_causa,
        "cobertura_causas": porcentaje(con_causa, len(diferencias)),
        "items_diferencia": diferencias,
    }


def filtrar_periodo(
    inventarios: list,
    desde: date | None,
    hasta: date,
    cliente: str = "",
    programacion: str = "todos",
    tipo_inventario: str = "todos",
) -> list:
    return [
        inventario
        for inventario in inventarios
        if (desde is None or fecha_cierre_reporte(inventario) >= desde)
        and fecha_cierre_reporte(inventario) <= hasta
        and (not cliente or inventario.cliente == cliente)
        and (
            tipo_inventario == "todos"
            or tipo_contenido_inventario(inventario) == tipo_inventario
        )
        and (
            programacion == "todos"
            or (
                programacion == "programado"
                and inventario_programado(inventario)
            )
            or (
                programacion == "no_programado"
                and not inventario_programado(inventario)
            )
        )
    ]


def construir_tipos_inventario(inventarios: list) -> list[dict]:
    nombres = {
        "piezas": "Piezas",
        "medios": "Medios",
        "materia_prima": "Materia prima",
    }
    agrupados: dict[str, list] = {codigo: [] for codigo in nombres}
    for inventario in inventarios:
        agrupados[tipo_contenido_inventario(inventario)].append(inventario)

    resultado = []
    for codigo, nombre in nombres.items():
        grupo = agrupados[codigo]
        metricas = resumen_items(grupo)
        resultado.append({
            "codigo": codigo,
            "nombre": nombre,
            "inventarios": len(grupo),
            "evaluados": metricas["evaluados"],
            "confiabilidad": metricas["confiabilidad"],
            "diferencias": metricas["diferencias"],
        })
    return resultado


def etiqueta_semana(inicio: date, fin: date) -> str:
    if inicio.month == fin.month:
        return f"{inicio.day}–{fin.day}/{fin.month}"
    return f"{inicio.day}/{inicio.month}–{fin.day}/{fin.month}"


def construir_tendencia(
    inventarios: list,
    desde: date | None,
    hasta: date,
    dias: int,
    agrupacion: str = "semanal",
) -> list[dict]:
    if not inventarios:
        return []
    grupos: dict[tuple, list] = defaultdict(list)
    if agrupacion == "diaria":
        for inventario in inventarios:
            fecha = fecha_inventario(inventario)
            grupos[("D", fecha.year, fecha.month, fecha.day)].append(inventario)
    elif agrupacion == "semanal":
        base = min(fecha_inventario(item) for item in inventarios)
        for inventario in inventarios:
            indice = (fecha_inventario(inventario) - base).days // 7
            grupos[("S", indice)].append(inventario)
    else:
        for inventario in inventarios:
            fecha = fecha_cierre_reporte(inventario)
            grupos[("M", fecha.year, fecha.month)].append(inventario)

    resultado = []
    for clave in sorted(grupos):
        grupo = grupos[clave]
        metricas = resumen_items(grupo)
        if clave[0] == "D":
            _tipo, anio, mes, dia = clave
            fecha = date(anio, mes, dia)
            etiqueta = f"{dia:02d}/{mes:02d}"
            periodo = fecha.isoformat()
        elif clave[0] == "S":
            inicio = min(
                fecha_inventario(item) for item in inventarios
            ) + timedelta(days=clave[1] * 7)
            fin = inicio + timedelta(days=6)
            etiqueta = etiqueta_semana(inicio, fin)
            periodo = inicio.isoformat()
        else:
            _tipo, anio, mes = clave
            etiqueta = f"{mes:02d}/{str(anio)[2:]}"
            periodo = f"{anio:04d}-{mes:02d}-01"
        resultado.append({
            "periodo": periodo,
            "etiqueta": etiqueta,
            "confiabilidad": metricas["confiabilidad"],
            "inventarios": len(grupo),
            "evaluados": metricas["evaluados"],
        })
    return resultado


def construir_clientes(
    actuales: list,
    anteriores: list,
) -> list[dict]:
    por_cliente_actual: dict[str, list] = defaultdict(list)
    por_cliente_anterior: dict[str, list] = defaultdict(list)
    for inventario in actuales:
        por_cliente_actual[inventario.cliente].append(inventario)
    for inventario in anteriores:
        por_cliente_anterior[inventario.cliente].append(inventario)

    resultado = []
    for cliente, inventarios in por_cliente_actual.items():
        actual = resumen_items(inventarios)
        anterior = resumen_items(por_cliente_anterior.get(cliente, []))
        tendencia = None
        if (
            actual["confiabilidad"] is not None
            and anterior["confiabilidad"] is not None
        ):
            tendencia = actual["confiabilidad"] - anterior["confiabilidad"]
        resultado.append({
            "cliente": cliente,
            "inventarios": len(inventarios),
            "evaluados": actual["evaluados"],
            "confiabilidad": actual["confiabilidad"],
            "diferencias": actual["diferencias"],
            "ajustes_pendientes": actual["ajustes_pendientes"],
            "tendencia": tendencia,
        })
    return sorted(
        resultado,
        key=lambda item: (
            item["confiabilidad"] is None,
            item["confiabilidad"] or 0,
            -item["ajustes_pendientes"],
        ),
    )


def construir_grafico_clientes(inventarios: list) -> list[dict]:
    por_cliente: dict[str, list] = defaultdict(list)
    for inventario in inventarios:
        por_cliente[inventario.cliente or "Sin cliente"].append(inventario)

    resultado = []
    for cliente, grupo in por_cliente.items():
        programados = [item for item in grupo if inventario_programado(item)]
        no_programados = [
            item for item in grupo if not inventario_programado(item)
        ]

        def serie(items: list) -> dict:
            metricas = resumen_items(items)
            return {
                "confiabilidad": metricas["confiabilidad"],
                "inventarios": len(items),
                "evaluados": metricas["evaluados"],
            }

        resultado.append({
            "cliente": cliente,
            "programado": serie(programados),
            "no_programado": serie(no_programados),
        })
    return sorted(resultado, key=lambda item: item["cliente"].casefold())


def construir_causas(
    inventarios: list,
    nombres_causas: dict[str, dict],
) -> list[dict]:
    metricas = resumen_items(inventarios)
    agrupadas: dict[str, dict] = {}
    for item, _metrica in metricas["items_diferencia"]:
        codigo = item.causa_diferencia_codigo or "SIN_CAUSA"
        datos = agrupadas.setdefault(
            codigo,
            {
                "codigo": codigo,
                "nombre": (
                    "Sin causa asignada"
                    if codigo == "SIN_CAUSA"
                    else nombres_causas.get(codigo, {}).get("nombre", codigo)
                ),
                "categoria": (
                    "PENDIENTE"
                    if codigo == "SIN_CAUSA"
                    else nombres_causas.get(codigo, {}).get(
                        "categoria",
                        "OTRA",
                    )
                ),
                "cantidad": 0,
                "ajustados": 0,
            },
        )
        datos["cantidad"] += 1
        datos["ajustados"] += int(item.ajustado_sistema)

    total = metricas["diferencias"]
    resultado = []
    for datos in agrupadas.values():
        datos["pendientes"] = datos["cantidad"] - datos["ajustados"]
        datos["porcentaje"] = porcentaje(datos["cantidad"], total)
        resultado.append(datos)
    return sorted(
        resultado,
        key=lambda item: (-item["cantidad"], item["nombre"]),
    )[:8]


def construir_alertas(
    actuales: list,
    clientes: list[dict],
    programaciones: list,
    *,
    alerta_cliente_pct: float,
    minimo_renglones_alerta: int,
) -> list[dict]:
    alertas = []
    for cliente in clientes:
        if (
            cliente["confiabilidad"] is not None
            and cliente["confiabilidad"] < alerta_cliente_pct
            and cliente["evaluados"] >= minimo_renglones_alerta
        ):
            alertas.append({
                "tipo": "CLIENTE",
                "nivel": "ALTO",
                "titulo": f'Confiabilidad baja · {cliente["cliente"]}',
                "detalle": (
                    f'{cliente["confiabilidad"]:.1f}% en '
                    f'{cliente["evaluados"]} renglones evaluados'
                ),
            })

    for inventario in actuales:
        metricas = resumen_items([inventario])
        if metricas["ajustes_pendientes"]:
            alertas.append({
                "tipo": "AJUSTE",
                "nivel": "MEDIO",
                "titulo": f'{inventario.codigo} tiene ajustes pendientes',
                "detalle": (
                    f'{inventario.cliente} · '
                    f'{metricas["ajustes_pendientes"]} diferencias sin ajustar'
                ),
            })

    sin_causa = sum(
        not item.causa_diferencia_codigo
        for inventario in actuales
        for item, _metrica in resumen_items([inventario])["items_diferencia"]
    )
    if sin_causa:
        alertas.append({
            "tipo": "CAUSA",
            "nivel": "MEDIO",
            "titulo": "Diferencias sin causa asignada",
            "detalle": f"{sin_causa} renglones todavía no fueron analizados",
        })

    hoy = date.today()
    vencidas = [
        item
        for item in programaciones
        if item.activa and item.fecha_proxima < hoy
    ]
    if vencidas:
        alertas.append({
            "tipo": "PROGRAMACION",
            "nivel": "MEDIO",
            "titulo": "Programaciones vencidas",
            "detalle": f"{len(vencidas)} inventarios esperan ser generados",
        })

    apariciones: dict[str, set[int]] = defaultdict(set)
    descripciones: dict[str, str] = {}
    for inventario in actuales:
        for item, _metrica in resumen_items([inventario])["items_diferencia"]:
            apariciones[item.codigo].add(inventario.id)
            descripciones[item.codigo] = item.descripcion
    repetidas = sorted(
        (
            (codigo, ids)
            for codigo, ids in apariciones.items()
            if len(ids) >= 2
        ),
        key=lambda item: (-len(item[1]), item[0]),
    )[:5]
    for codigo, ids in repetidas:
        alertas.append({
            "tipo": "REPETICION",
            "nivel": "MEDIO",
            "titulo": f"Diferencia repetida · {codigo}",
            "detalle": (
                f"{descripciones.get(codigo, '')} · "
                f"{len(ids)} inventarios del período"
            ),
        })
    prioridad = {"ALTO": 0, "MEDIO": 1, "BAJO": 2}
    return sorted(
        alertas,
        key=lambda item: prioridad.get(item["nivel"], 9),
    )[:12]


def generar_reporte(
    inventarios_cerrados: list,
    causas: list,
    programaciones: list,
    *,
    dias: int,
    cliente: str,
    mes_cierre: str = "",
    programacion: str = "todos",
    tipo_inventario: str = "todos",
    agrupacion: str = "semanal",
    configuracion: dict,
) -> dict:
    hoy = date.today()
    if mes_cierre:
        desde, hasta = limites_mes(mes_cierre)
    else:
        desde = hoy - timedelta(days=dias - 1) if dias else None
        hasta = hoy
    actuales = filtrar_periodo(
        inventarios_cerrados,
        desde,
        hasta,
        cliente,
        programacion,
        tipo_inventario,
    )
    if mes_cierre:
        inicio_anterior = mes_anterior(desde)
        _inicio, fin_anterior = limites_mes(
            inicio_anterior.strftime("%Y-%m")
        )
        anteriores = filtrar_periodo(
            inventarios_cerrados,
            inicio_anterior,
            fin_anterior,
            cliente,
            programacion,
            tipo_inventario,
        )
    elif dias:
        fin_anterior = desde - timedelta(days=1)
        inicio_anterior = fin_anterior - timedelta(days=dias - 1)
        anteriores = filtrar_periodo(
            inventarios_cerrados,
            inicio_anterior,
            fin_anterior,
            cliente,
            programacion,
            tipo_inventario,
        )
    else:
        anteriores = []

    meses_disponibles = {
        fecha_cierre_reporte(inventario).strftime("%Y-%m")
        for inventario in inventarios_cerrados
    }
    meses_disponibles.add(hoy.strftime("%Y-%m"))
    meses_disponibles.add(mes_anterior(hoy).strftime("%Y-%m"))
    if mes_cierre:
        meses_disponibles.add(mes_cierre)
    reasignados_mes = sum(
        fecha_inventario(inventario).strftime("%Y-%m") != mes_cierre
        for inventario in actuales
        if mes_cierre
    )

    general = resumen_items(actuales)
    general["inventarios"] = len(actuales)
    general.pop("items_diferencia", None)
    clientes = construir_clientes(actuales, anteriores)
    nombres_causas = {
        causa.codigo: {
            "nombre": causa.nombre,
            "categoria": causa.categoria,
        }
        for causa in causas
    }
    todos_clientes = sorted({
        inventario.cliente
        for inventario in inventarios_cerrados
        if inventario.cliente
    })
    programaciones_relevantes = [
        programacion
        for programacion in programaciones
        if (
            not cliente
            or (
                getattr(programacion, "plantilla", None) is not None
                and programacion.plantilla.cliente == cliente
            )
        )
        and (
            tipo_inventario == "todos"
            or (
                getattr(programacion, "plantilla", None) is not None
                and tipo_contenido_inventario(programacion.plantilla)
                == tipo_inventario
            )
        )
    ]
    return {
        "configuracion": configuracion,
        "filtros": {
            "dias": dias,
            "mes_cierre": mes_cierre,
            "meses_cierre": sorted(meses_disponibles, reverse=True),
            "reasignados_mes": reasignados_mes,
            "cliente": cliente,
            "programacion": programacion,
            "tipo_inventario": tipo_inventario,
            "agrupacion": agrupacion,
            "desde": desde.isoformat() if desde else None,
            "hasta": hasta.isoformat(),
            "clientes": todos_clientes,
        },
        "general": general,
        "tipos_inventario": construir_tipos_inventario(actuales),
        "tendencia": construir_tendencia(
            actuales,
            desde,
            hasta,
            dias,
            agrupacion,
        ),
        "clientes": clientes,
        "clientes_grafico": construir_grafico_clientes(actuales),
        "causas": construir_causas(actuales, nombres_causas),
        "alertas": construir_alertas(
            actuales,
            clientes,
            programaciones_relevantes,
            alerta_cliente_pct=float(
                configuracion["alerta_cliente_pct"]
            ),
            minimo_renglones_alerta=int(
                configuracion["minimo_renglones_alerta"]
            ),
        ),
    }
