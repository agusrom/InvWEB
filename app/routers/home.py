"""Lecturas acotadas para la portada; no requiere migraciones ni índices nuevos."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.database import get_db
from app.services.client_catalog import nombres_equivalentes
from app.models import Inventario
from app.routers.api import buscar_inventario
from app.serializers import inventario_dict, items_inventario_dict
from app.services.inventory_listing import cabecera, inventarios_calendario, listar_inventarios, metricas_portada

router = APIRouter(prefix="/api/portada", tags=["Portada"])


@router.get("/inventarios")
def listado(pagina: int = Query(1, ge=1), por_pagina: int = Query(25, ge=1, le=100),
            buscar: str = Query("", max_length=200),
            estado: str = Query("Todos", pattern="^(Todos|En preparación|En conteo|Cerrado)$"),
            vista: str = Query("EN_CURSO", pattern="^(EN_CURSO|REALIZADOS|TODOS)$"),
            db: Session = Depends(get_db)):
    return listar_inventarios(db, pagina, por_pagina, buscar, estado, vista)


@router.get("/metricas")
def metricas(db: Session = Depends(get_db)):
    return metricas_portada(db)


@router.get("/calendario")
def calendario(desde: date, hasta: date, db: Session = Depends(get_db)):
    if hasta < desde or (hasta - desde).days > 62:
        raise HTTPException(status_code=422, detail="El calendario admite rangos de hasta 63 días")
    return {"inventarios": inventarios_calendario(db, desde, hasta)}


@router.get("/detalle/{inventario_id}")
def detalle(inventario_id: int, db: Session = Depends(get_db)):
    inv = buscar_inventario(db, inventario_id)
    datos = inventario_dict(inv)
    ids = [r["inventario_reconteo_id"] for r in datos["reconteos_vinculados"]]
    if datos["relacion_reconteo"]:
        ids.append(datos["relacion_reconteo"]["inventario_origen_id"])
    datos["inventarios_relacionados"] = [cabecera(row) for row in db.scalars(
        select(Inventario).where(Inventario.id.in_(ids))).all()] if ids else []
    return datos


@router.get("/historial/{inventario_id}")
def historial(inventario_id: int, db: Session = Depends(get_db)):
    actual = buscar_inventario(db, inventario_id)
    comparables = db.scalars(select(Inventario).where(
        Inventario.id != actual.id, Inventario.cliente.in_(nombres_equivalentes(actual.cliente)),
        Inventario.categoria == actual.categoria, Inventario.modalidad_conteo == actual.modalidad_conteo,
        Inventario.fecha <= actual.fecha,
    ).options(selectinload(Inventario.items)).order_by(Inventario.fecha.desc(), Inventario.id.desc())).all()
    return {"inventarios": [{**cabecera(inv), "items": items_inventario_dict(inv)} for inv in comparables]}
