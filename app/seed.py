from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CausaDiferencia,
    Conciliacion,
    ConciliacionItem,
    Inventario,
    InventarioItem,
    Plantilla,
    PlantillaItem,
)
from app.constants import CAUSAS_DIFERENCIA_PREDEFINIDAS


PLANTILLAS_DEMO = [
    {
        "nombre": "Conteo mensual - Autopartes Norte",
        "cliente": "Autopartes Norte",
        "descripcion": "Piezas terminadas y subconjuntos",
        "items": [
            ("AN-1042", "Soporte lateral", "A-01-02", 126),
            ("AN-2088", "Refuerzo central", "A-01-04", 84),
            ("AN-3110", "Conjunto bisagra", "A-02-01", 52),
        ],
    },
    {
        "nombre": "Inventario general - MetalSur",
        "cliente": "MetalSur",
        "descripcion": "Material productivo por ubicación",
        "items": [
            ("MS-4401", "Placa estampada", "B-03-02", 230),
            ("MS-4475", "Perfil mecanizado", "B-03-05", 96),
            ("MS-5520", "Conjunto soldado", "B-04-01", 41),
        ],
    },
    {
        "nombre": "Control semanal - Cliente Delta",
        "cliente": "Cliente Delta",
        "descripcion": "Piezas críticas de entrega",
        "items": [
            ("CD-0127", "Brida de fijación", "C-02-03", 74),
            ("CD-0184", "Tapa protectora", "C-02-04", 118),
            ("CD-0202", "Soporte superior", "C-02-06", 63),
        ],
    },
]


def cargar_datos_demo(db: Session) -> None:
    for datos in CAUSAS_DIFERENCIA_PREDEFINIDAS:
        causa = db.get(CausaDiferencia, datos["codigo"])
        if causa is None:
            db.add(CausaDiferencia(**datos))
        elif causa.categoria == "OTRA" and datos["categoria"] != "OTRA":
            causa.categoria = datos["categoria"]
    db.flush()

    if db.scalar(select(Plantilla.id).limit(1)) is not None:
        db.commit()
        return

    plantillas: list[Plantilla] = []
    for datos in PLANTILLAS_DEMO:
        plantilla = Plantilla(
            nombre=datos["nombre"],
            cliente=datos["cliente"],
            descripcion=datos["descripcion"],
        )
        plantilla.items = [
            PlantillaItem(
                codigo=codigo,
                descripcion=descripcion,
                ubicacion=ubicacion,
                stock_referencia=stock,
            )
            for codigo, descripcion, ubicacion, stock in datos["items"]
        ]
        db.add(plantilla)
        plantillas.append(plantilla)

    db.flush()

    ejemplos = [
        ("INV-2026-014", plantillas[0], date(2026, 7, 27), "Agustín Romero", "En preparación", [None, None, None]),
        ("INV-2026-013", plantillas[1], date(2026, 7, 25), "Lucía M.", "En conteo", [228, 92, None]),
        ("INV-2026-012", plantillas[2], date(2026, 7, 18), "Martín P.", "Cerrado", [74, 120, 63]),
        ("INV-2026-011", plantillas[2], date(2026, 7, 11), "Martín P.", "Cerrado", [70, 115, 60]),
    ]

    inventarios: dict[str, Inventario] = {}
    for codigo, plantilla, fecha, responsable, estado, conteos in ejemplos:
        inventario = Inventario(
            codigo=codigo,
            cliente=plantilla.cliente,
            plantilla_id=plantilla.id,
            fecha=fecha,
            responsable=responsable,
            estado=estado,
        )
        inventario.items = [
            InventarioItem(
                codigo=item.codigo,
                descripcion=item.descripcion,
                ubicacion=item.ubicacion,
                stock_sistema=item.stock_referencia,
                conteo_fisico=conteos[indice],
            )
            for indice, item in enumerate(plantilla.items)
        ]
        db.add(inventario)
        inventarios[codigo] = inventario

    db.flush()
    conciliacion = Conciliacion(
        codigo="CON-2026-001",
        nombre="Ejemplo visita Cliente Delta",
        inventario_inicial_id=inventarios["INV-2026-011"].id,
        inventario_final_id=inventarios["INV-2026-012"].id,
        inventario_inicial_codigo="INV-2026-011",
        inventario_final_codigo="INV-2026-012",
        fecha_inicial=date(2026, 7, 11),
        fecha_final=date(2026, 7, 18),
    )
    movimientos = [(10, 6), (8, 3), (5, 1)]
    conciliacion.items = [
        ConciliacionItem(
            codigo=item.codigo,
            descripcion=item.descripcion,
            stock_inicial=float(conteo_inicial),
            detalle_inicial=f"{item.codigo}: {conteo_inicial} × 1 = {conteo_inicial}",
            ingresos=float(movimientos[indice][0]),
            egresos=float(movimientos[indice][1]),
            stock_final=float(conteo_final),
            detalle_final=f"{item.codigo}: {conteo_final} × 1 = {conteo_final}",
        )
        for indice, (item, conteo_inicial, conteo_final) in enumerate(zip(
            plantillas[2].items,
            [70, 115, 60],
            [74, 120, 63],
        ))
    ]
    db.add(conciliacion)

    db.commit()
