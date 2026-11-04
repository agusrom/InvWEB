"""Notas compartidas de preparación, guardadas localmente en SQLite."""
from fastapi import APIRouter, HTTPException, Response

from app import schedule_notes_store as store
from app.schemas import NotaCronogramaEntrada

router = APIRouter(prefix="/api/notas-cronograma", tags=["Notas del cronograma"])


def guardar_nota(datos: NotaCronogramaEntrada, nota_id: int | None = None):
    if not datos.titulo.strip():
        raise HTTPException(status_code=422, detail="Escribí un título para la nota")
    nota = store.guardar_nota(datos, nota_id)
    if nota is None:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    return nota


@router.post("", status_code=201)
def crear_nota(datos: NotaCronogramaEntrada):
    return guardar_nota(datos)


@router.put("/{nota_id}")
def actualizar_nota(nota_id: int, datos: NotaCronogramaEntrada):
    return guardar_nota(datos, nota_id)


@router.delete("/{nota_id}", status_code=204)
def eliminar_nota(nota_id: int):
    if not store.eliminar_nota(nota_id):
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    return Response(status_code=204)
