"""Consultas de portada: solo lectura, sin cargar renglones en el navegador."""
from app.services.client_catalog import referencia as referencia_cliente, nombres_para_busqueda
from datetime import date
from math import ceil
from sqlalchemy import Date, and_, case, column, func, literal, or_, select, table
from sqlalchemy.orm import raiseload

from app.models import Inventario, InventarioItem
from app.services.indicator_settings import cargar_configuracion


def cabecera(inv, mes_cierre=None):
    return {
        "id": inv.id, "codigo": inv.codigo, "cliente": inv.cliente, **referencia_cliente(inv.cliente),
        "fecha": inv.fecha.isoformat(),
        "fecha_programada": inv.fecha_programada.isoformat() if inv.fecha_programada else None,
        **({"mes_cierre": mes_cierre.isoformat()} if mes_cierre else {}),
        "cerrado_en": inv.cerrado_en.isoformat() if inv.cerrado_en else None,
        "programacion_id": inv.programacion_id, "estado": inv.estado,
        "categoria": inv.categoria, "tipo_inventario_codigo": inv.tipo_inventario_codigo,
        "modalidad_conteo": inv.modalidad_conteo, "ambito": inv.ambito,
        "responsable": inv.responsable, "colaboradores": inv.colaboradores,
    }


def condiciones_metricas(tolerancia):
    item = InventarioItem
    evaluado = and_(item.stock_pendiente.is_not(True), item.conteo_fisico.is_not(None))
    ok = and_(evaluado, or_(
        and_(item.stock_sistema == 0, item.conteo_fisico == 0),
        and_(item.stock_sistema != 0,
             func.abs((item.conteo_fisico - item.stock_sistema) * 100.0 /
                      func.nullif(item.stock_sistema, 0)) <= tolerancia + 1e-9),
    ))
    return evaluado, ok


def sum_if(condition):
    return func.sum(case((condition, 1), else_=0))


def listar_inventarios(db, pagina=1, por_pagina=25, buscar="", estado="Todos", vista="EN_CURSO"):
    filters = []
    if estado != "Todos":
        filters.append(Inventario.estado == estado)
    if vista == "EN_CURSO":
        filters.append(Inventario.estado != "Cerrado")
    elif vista == "REALIZADOS":
        filters.append(Inventario.estado == "Cerrado")
    if buscar.strip():
        fields = [Inventario.codigo, Inventario.cliente, Inventario.responsable,
                  Inventario.colaboradores, Inventario.observaciones,
                  case((Inventario.ambito == "CLIENTE", "Con cliente"), else_="Interno")]
        searchable = func.coalesce(fields[0], "")
        for field in fields[1:]:
            searchable = searchable + literal(" ") + func.coalesce(field, "")
        filters.append(or_(func.lower(searchable).contains(buscar.strip().lower(), autoescape=True),
                           Inventario.cliente.in_(nombres_para_busqueda(buscar))))
    total = db.scalar(select(func.count()).select_from(Inventario).where(*filters))
    paginas = max(1, ceil(total / por_pagina))
    pagina = min(pagina, paginas)
    rows = db.scalars(select(Inventario).where(*filters).options(raiseload("*"))
                      .order_by(Inventario.fecha.desc(), Inventario.id.desc())
                      .limit(por_pagina).offset((pagina - 1) * por_pagina)).all()
    result = []
    if rows:
        evaluado, ok = condiciones_metricas(float(cargar_configuracion(db)["tolerancia_pct"]))
        metrics = db.execute(select(
            InventarioItem.inventario_id,
            func.count().label("total"),
            sum_if(InventarioItem.conteo_fisico.is_not(None)).label("contados"),
            sum_if(InventarioItem.stock_pendiente.is_not(True)).label("evaluables"),
            sum_if(evaluado).label("evaluados"), sum_if(ok).label("correctos"),
            sum_if(and_(evaluado, InventarioItem.conteo_fisico != InventarioItem.stock_sistema)).label("diferencias"),
            sum_if(and_(evaluado, ~ok)).label("fuera"),
            sum_if(InventarioItem.stock_pendiente.is_(True)).label("stock_pendiente"),
        ).where(InventarioItem.inventario_id.in_([row.id for row in rows]))
         .group_by(InventarioItem.inventario_id)).mappings().all()
        by_id = {row["inventario_id"]: row for row in metrics}
        cierres = table("inventario_cierres", column("inventario_id"), column("mes_cierre", Date))
        meses = dict(db.execute(select(cierres.c.inventario_id, cierres.c.mes_cierre)
                     .where(cierres.c.inventario_id.in_([row.id for row in rows]))).all())
        for inv in rows:
            m = by_id.get(inv.id, {})
            n, counted, evaluables = int(m.get("total", 0)), int(m.get("contados", 0)), int(m.get("evaluables", 0))
            evaluated, correct = int(m.get("evaluados", 0)), int(m.get("correctos", 0))
            result.append({**cabecera(inv, meses.get(inv.id) or date(inv.fecha.year, inv.fecha.month, 1)),
                "progreso": round(counted * 100 / n) if n else 0,
                "items_ok": correct, "items_evaluados": evaluated, "items_evaluables": evaluables,
                "confiabilidad": correct * 100 / evaluables if evaluables else None,
                "confiabilidad_completa": bool(evaluables) and evaluated == evaluables,
                "resumen": {"total": n, "contados": counted, "pendientes": n - counted,
                            "diferencias": int(m.get("diferencias", 0)),
                            "fueraTolerancia": int(m.get("fuera", 0)),
                            "stockPendiente": int(m.get("stock_pendiente", 0))},
            })
    return {"inventarios": result, "pagina": pagina, "por_pagina": por_pagina,
            "paginas": paginas, "total": total}


def metricas_portada(db):
    diferencia = select(InventarioItem.id).where(
        InventarioItem.inventario_id == Inventario.id,
        InventarioItem.stock_pendiente.is_not(True), InventarioItem.conteo_fisico.is_not(None),
        InventarioItem.conteo_fisico != InventarioItem.stock_sistema,
    ).exists()
    row = db.execute(select(
        func.count(Inventario.id).label("total"),
        sum_if(Inventario.estado == "En preparación").label("preparacion"),
        sum_if(Inventario.estado == "En conteo").label("conteo"),
        sum_if(diferencia).label("diferencias"),
    ).select_from(Inventario)).mappings().one()
    return {key: int(value or 0) for key, value in row.items()}


def inventarios_calendario(db, desde, hasta):
    return [cabecera(inv) for inv in db.scalars(select(Inventario).options(raiseload("*"))
        .where(or_(Inventario.fecha.between(desde, hasta), Inventario.fecha_programada.between(desde, hasta)))
        .order_by(Inventario.fecha, Inventario.id)).all()]
