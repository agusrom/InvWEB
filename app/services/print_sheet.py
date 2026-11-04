from app.models import Inventario


def filas_planilla_impresion(inventario: Inventario) -> list[dict]:
    """Agrupa el detalle interno en una sola fila imprimible por pieza."""
    piezas: dict[str, dict] = {}

    for item in inventario.items:
        codigo_material = (item.codigo_material or "").strip()

        pieza = piezas.setdefault(
            item.codigo,
            {
                "codigo": item.codigo,
                "codigo_cliente": item.codigo_cliente or "",
                "descripcion": item.descripcion or "",
                "uso": float(item.uso if item.uso is not None else 1),
                "codigo_material": codigo_material,
                "ubicacion": item.ubicacion or "",
                "operaciones": [],
                "lotes": "",
                "material_contado": False,
                "tipo_estructura": item.tipo_estructura or "INDEPENDIENTE",
            },
        )

        if item.etapa in {"OPERACION", "PROCESO_GLOBAL"}:
            detalle = " · ".join(
                parte
                for parte in [
                    (item.operacion or "").strip(),
                    (item.titulo_operacion or "").strip(),
                ]
                if parte
            )
            if detalle and detalle not in pieza["operaciones"]:
                pieza["operaciones"].append(detalle)

        if item.etapa == "MATERIAL":
            pieza["material_contado"] = True
            if "Lotes:" in (item.titulo_operacion or ""):
                pieza["lotes"] = (
                    item.titulo_operacion.split("Lotes:", 1)[1].strip()
                )

    return list(piezas.values())


def filas_detalle_impresion(inventario: Inventario) -> list[dict]:
    """Devuelve una fila imprimible por etapa u operación del inventario."""
    nombres_etapa = {
        "MATERIAL": "Material sin usar",
        "PROCESO_GLOBAL": "Proceso global",
        "OPERACION": "En proceso",
        "TERMINADO": "Pieza terminada",
    }

    return [
        {
            "codigo": (
                item.codigo_material
                if item.etapa == "MATERIAL" and item.codigo_material
                else item.codigo
            ),
            "codigo_cliente": (
                "" if item.etapa == "MATERIAL"
                else item.codigo_cliente or ""
            ),
            "descripcion": (
                "Materia prima"
                if item.etapa == "MATERIAL"
                else item.descripcion or ""
            ),
            "ubicacion": item.ubicacion or "",
            "etapa": nombres_etapa.get(item.etapa, item.etapa or ""),
            "operacion": " · ".join(
                parte
                for parte in [
                    (item.operacion or "").strip(),
                    (item.titulo_operacion or "").strip(),
                ]
                if parte
            ),
            "proveedor": item.proveedor or "",
            "tipo_estructura": (
                "INDEPENDIENTE"
                if item.etapa == "MATERIAL"
                else item.tipo_estructura or "INDEPENDIENTE"
            ),
        }
        for item in inventario.items
    ]


def filas_materia_prima_impresion(inventario: Inventario) -> list[dict]:
    """Agrupa los lotes en una sola ficha física por código de materia prima."""
    materiales: dict[str, dict] = {}
    for item in inventario.items:
        material = materiales.setdefault(
            item.codigo,
            {
                "codigo": item.codigo,
                "descripcion": item.descripcion or "",
                "diametro": item.diametro or "",
                "largo": item.largo or "",
                "espesor": item.espesor or "",
                "unidad": item.unidad or "",
                "ubicacion": item.ubicacion or "",
                "lotes_sistema": [],
            },
        )
        if item.lote and item.lote not in material["lotes_sistema"]:
            material["lotes_sistema"].append(item.lote)

    return list(materiales.values())


def filas_ciclico_impresion(inventario: Inventario) -> list[dict]:
    """Ordena cada punto de conteo según el nivel y ruta de la estructura."""
    nombres_etapa = {
        "MATERIAL": "Materia prima",
        "PROCESO_GLOBAL": "Proceso global",
        "OPERACION": "En proceso",
        "TERMINADO": "Pieza terminada",
    }
    filas = [
        {
            "codigo": item.codigo,
            "codigo_padre": item.codigo_padre or "",
            "nivel": item.nivel,
            "uso": item.uso,
            "ruta": item.ruta or item.codigo,
            "descripcion": item.descripcion or "",
            "etapa": nombres_etapa.get(item.etapa, item.etapa or ""),
            "operacion": " · ".join(
                parte
                for parte in [
                    (item.operacion or "").strip(),
                    (item.titulo_operacion or "").strip(),
                ]
                if parte
            ),
            "lote": item.lote or "",
            "unidad": item.unidad or "",
            "ubicacion": item.ubicacion or "",
            "tipo_estructura": item.tipo_estructura or "INDEPENDIENTE",
        }
        for item in inventario.items
    ]
    return sorted(
        filas,
        key=lambda fila: (
            fila["nivel"],
            fila["ruta"],
            fila["codigo"],
            fila["etapa"],
            fila["operacion"],
        ),
    )
