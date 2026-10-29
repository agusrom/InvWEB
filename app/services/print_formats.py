from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    ConfiguracionSistema,
    FormatoColumna,
    FormatoImpresion,
    FormatoVersion,
    Inventario,
)

ESTILO_COLUMNA_PREFIJO = "fce:"


FORMATOS_PREDEFINIDOS = {
    "FLUJO_HORIZONTAL": {
        "nombre": "Flujo horizontal por sectores",
        "descripcion": "Conteo de piezas por abastecimiento, línea y despacho.",
        "categoria": "PIEZAS",
        "orientacion": "HORIZONTAL",
        "altura": 15,
        "columnas": [
            ("codigo", "Cód. CGR", 9),
            ("uso", "Uso", 4),
            ("codigo_cliente", "Cód. cliente", 11),
            ("descripcion", "Descripción", 15),
            ("abastecimiento", "Abastecimiento", 13),
            ("despacho", "Despacho (dársena)", 16),
            ("linea", "Línea / proceso", 16),
            ("scrap", "Scrap", 7),
            ("stock_final", "Stock final", 9),
        ],
    },
    "RESUMEN_VERTICAL": {
        "nombre": "Resumen vertical",
        "descripcion": "Planilla resumida para inventarios grandes.",
        "categoria": "PIEZAS",
        "orientacion": "VERTICAL",
        "altura": 9,
        "columnas": [
            ("codigo", "Cód. CGR", 11),
            ("codigo_cliente", "Cód. cliente", 14),
            ("descripcion", "Descripción", 20),
            ("uso", "Uso", 5),
            ("abastecimiento", "Abastecimiento", 15),
            ("linea", "Línea / proceso", 10),
            ("despacho", "Despacho", 10),
            ("scrap", "Scrap", 7),
            ("stock_final", "Stock final", 8),
        ],
    },
    "DETALLE_ETAPAS": {
        "nombre": "Detalle por etapa",
        "descripcion": "Una fila por etapa u operación del inventario.",
        "categoria": "PIEZAS",
        "orientacion": "HORIZONTAL",
        "altura": 11,
        "columnas": [
            ("numero", "#", 3),
            ("codigo", "Cód. CGR", 11),
            ("codigo_cliente", "Cód. cliente", 11),
            ("descripcion", "Descripción", 16),
            ("etapa", "Etapa", 11),
            ("operacion", "Operación", 17),
            ("proveedor", "Proveedor", 9),
            ("ubicacion", "Ubicación", 9),
            ("conteo", "Conteo físico", 13),
        ],
    },
    "LISTADO_SIMPLE": {
        "nombre": "Listado simple",
        "descripcion": "Listado general con cantidad y observaciones.",
        "categoria": "TODAS",
        "orientacion": "HORIZONTAL",
        "altura": 14,
        "columnas": [
            ("numero", "#", 4),
            ("codigo", "Código", 14),
            ("codigo_cliente", "Cód. cliente", 15),
            ("descripcion", "Descripción", 25),
            ("ubicacion", "Ubicación", 12),
            ("conteo", "Cantidad", 13),
            ("observaciones", "Observaciones", 17),
        ],
    },
    "MEDIOS": {
        "nombre": "Conteo de medios",
        "descripcion": "Conteo de medios vacíos, llenos y rotos.",
        "categoria": "PIEZAS",
        "orientacion": "HORIZONTAL",
        "altura": 17,
        "columnas": [
            ("numero", "#", 4),
            ("codigo", "Cód. CGR", 15),
            ("codigo_cliente", "Cód. cliente", 18),
            ("descripcion", "Descripción", 33),
            ("vacios", "Vacíos", 10),
            ("llenos", "Llenos", 10),
            ("rotos", "Rotos", 10),
        ],
    },
    "CICLICO": {
        "nombre": "Estructura por nivel",
        "descripcion": "Inventario cíclico ordenado por nivel de estructura.",
        "categoria": "CICLICO",
        "orientacion": "HORIZONTAL",
        "altura": 10,
        "columnas": [
            ("nivel", "Nivel", 5),
            ("codigo", "Código", 13),
            ("padre", "Padre", 11),
            ("descripcion", "Descripción", 18),
            ("uso", "Uso acum.", 7),
            ("etapa", "Etapa", 10),
            ("operacion", "Operación / lote", 18),
            ("ubicacion", "Ubicación", 8),
            ("conteo", "Conteo físico", 10),
        ],
    },
}


def _crear_version_inicial(
    db: Session,
    formato: FormatoImpresion,
    definicion: dict,
) -> FormatoVersion:
    version = FormatoVersion(
        formato=formato,
        numero=1,
        nombre="Predeterminada",
        orientacion=definicion["orientacion"],
        margen_superior_mm=8,
        margen_derecho_mm=7,
        margen_inferior_mm=8,
        margen_izquierdo_mm=7,
        tamano_fuente_pt=8,
        altura_fila_mm=definicion["altura"],
        mostrar_firmas=True,
    )
    version.columnas = [
        FormatoColumna(
            clave=clave,
            titulo=titulo,
            orden=orden,
            visible=True,
            ancho_pct=ancho,
        )
        for orden, (clave, titulo, ancho) in enumerate(
            definicion["columnas"],
            start=1,
        )
    ]
    db.add(version)
    return version


def asegurar_formatos_impresion(db: Session) -> None:
    for codigo, definicion in FORMATOS_PREDEFINIDOS.items():
        formato = db.scalar(
            select(FormatoImpresion)
            .where(FormatoImpresion.codigo == codigo)
            .options(selectinload(FormatoImpresion.versiones))
        )
        if formato is None:
            formato = FormatoImpresion(
                codigo=codigo,
                nombre=definicion["nombre"],
                descripcion=definicion["descripcion"],
                categoria=definicion["categoria"],
            )
            db.add(formato)
            db.flush()
        if not formato.versiones:
            _crear_version_inicial(db, formato, definicion)
        for version in formato.versiones:
            if not (version.nombre or "").strip():
                version.nombre = (
                    "Predeterminada"
                    if version.numero == 1
                    else f"Versión {version.numero}"
                )
    db.commit()

    actuales = {
        formato.codigo: formato.versiones[-1].id
        for formato in db.scalars(
            select(FormatoImpresion)
            .options(selectinload(FormatoImpresion.versiones))
        ).all()
        if formato.versiones
    }
    inventarios = db.scalars(
        select(Inventario).where(Inventario.formato_version_id.is_(None))
    ).all()
    for inventario in inventarios:
        inventario.formato_version_id = actuales.get(
            inventario.formato_impresion
        )
    db.commit()


def _clave_estilo(version_id: int, clave_columna: str) -> str:
    return f"{ESTILO_COLUMNA_PREFIJO}{version_id}:{clave_columna}"


def _cargar_estilos(
    db: Session,
    versiones: list[FormatoVersion],
) -> None:
    ids = {version.id for version in versiones if version.id is not None}
    estilos_por_version: dict[int, dict[str, dict]] = {
        version_id: {} for version_id in ids
    }
    if ids:
        registros = db.scalars(
            select(ConfiguracionSistema).where(
                ConfiguracionSistema.clave.like(
                    f"{ESTILO_COLUMNA_PREFIJO}%"
                )
            )
        ).all()
        for registro in registros:
            partes = registro.clave.split(":", 2)
            if len(partes) != 3:
                continue
            try:
                version_id = int(partes[1])
                estilo = json.loads(registro.valor)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if version_id not in ids or not isinstance(estilo, dict):
                continue
            estilos_por_version[version_id][partes[2]] = estilo
    for version in versiones:
        version._estilos_columnas = estilos_por_version.get(version.id, {})


def version_dict(version: FormatoVersion) -> dict:
    estilos = getattr(version, "_estilos_columnas", {})
    return {
        "id": version.id,
        "numero": version.numero,
        "nombre": version.nombre,
        "orientacion": version.orientacion,
        "margen_superior_mm": version.margen_superior_mm,
        "margen_derecho_mm": version.margen_derecho_mm,
        "margen_inferior_mm": version.margen_inferior_mm,
        "margen_izquierdo_mm": version.margen_izquierdo_mm,
        "tamano_fuente_pt": version.tamano_fuente_pt,
        "altura_fila_mm": version.altura_fila_mm,
        "mostrar_firmas": version.mostrar_firmas,
        "creada_en": version.creada_en.isoformat() if version.creada_en else None,
        "columnas": [
            {
                "clave": columna.clave,
                "titulo": columna.titulo,
                "orden": columna.orden,
                "visible": columna.visible,
                "ancho_pct": columna.ancho_pct,
                "tamano_fuente_pt": float(
                    estilos.get(columna.clave, {}).get(
                        "tamano_fuente_pt",
                        version.tamano_fuente_pt,
                    )
                ),
                "negrita": bool(
                    estilos.get(columna.clave, {}).get(
                        "negrita",
                        columna.clave == "codigo",
                    )
                ),
            }
            for columna in sorted(version.columnas, key=lambda item: item.orden)
        ],
    }


def formato_dict(formato: FormatoImpresion, detalle: bool = False) -> dict:
    actual = formato.versiones[-1] if formato.versiones else None
    resultado = {
        "id": formato.id,
        "codigo": formato.codigo,
        "nombre": formato.nombre,
        "descripcion": formato.descripcion,
        "categoria": formato.categoria,
        "editable": formato.editable,
        "activo": formato.activo,
        "version_actual": actual.numero if actual else 0,
    }
    if detalle:
        resultado["configuracion"] = version_dict(actual) if actual else None
        resultado["versiones"] = [
            version_dict(version)
            for version in sorted(
                formato.versiones,
                key=lambda item: item.numero,
                reverse=True,
            )
        ]
    return resultado


def listar_formatos(db: Session) -> list[FormatoImpresion]:
    return list(
        db.scalars(
            select(FormatoImpresion)
            .where(FormatoImpresion.activo.is_(True))
            .options(
                selectinload(FormatoImpresion.versiones)
                .selectinload(FormatoVersion.columnas)
            )
            .order_by(FormatoImpresion.nombre)
        ).all()
    )


def obtener_formato(db: Session, codigo: str) -> FormatoImpresion | None:
    formato = db.scalar(
        select(FormatoImpresion)
        .where(FormatoImpresion.codigo == codigo)
        .options(
            selectinload(FormatoImpresion.versiones)
            .selectinload(FormatoVersion.columnas)
        )
    )
    if formato:
        _cargar_estilos(db, list(formato.versiones))
    return formato


def crear_version(
    db: Session,
    formato: FormatoImpresion,
    configuracion: dict,
) -> FormatoVersion:
    columnas = configuracion["columnas"]
    total_visible = sum(
        float(columna["ancho_pct"])
        for columna in columnas
        if columna["visible"]
    )
    numero = int(
        db.scalar(
            select(func.max(FormatoVersion.numero))
            .where(FormatoVersion.formato_id == formato.id)
        )
        or 0
    ) + 1
    version = FormatoVersion(
        formato_id=formato.id,
        numero=numero,
        nombre=configuracion["nombre"].strip(),
        orientacion=configuracion["orientacion"],
        margen_superior_mm=configuracion["margen_superior_mm"],
        margen_derecho_mm=configuracion["margen_derecho_mm"],
        margen_inferior_mm=configuracion["margen_inferior_mm"],
        margen_izquierdo_mm=configuracion["margen_izquierdo_mm"],
        tamano_fuente_pt=configuracion["tamano_fuente_pt"],
        altura_fila_mm=configuracion["altura_fila_mm"],
        mostrar_firmas=configuracion["mostrar_firmas"],
    )
    version.columnas = [
        FormatoColumna(
            clave=columna["clave"],
            titulo=columna["titulo"].strip(),
            orden=orden,
            visible=columna["visible"],
            ancho_pct=(
                float(columna["ancho_pct"]) * 100 / total_visible
                if columna["visible"]
                else float(columna["ancho_pct"])
            ),
        )
        for orden, columna in enumerate(columnas, start=1)
    ]
    db.add(version)
    db.flush()
    for columna in columnas:
        tamano = columna.get("tamano_fuente_pt")
        if tamano is None:
            tamano = configuracion["tamano_fuente_pt"]
        db.add(
            ConfiguracionSistema(
                clave=_clave_estilo(version.id, columna["clave"]),
                valor=json.dumps(
                    {
                        "tamano_fuente_pt": float(tamano),
                        "negrita": bool(columna.get("negrita", False)),
                    },
                    separators=(",", ":"),
                ),
                descripcion=(
                    "Estilo de columna de una versión de impresión."
                ),
            )
        )
    db.commit()
    db.refresh(version)
    version_guardada = db.scalar(
        select(FormatoVersion)
        .where(FormatoVersion.id == version.id)
        .options(selectinload(FormatoVersion.columnas))
    )
    _cargar_estilos(db, [version_guardada])
    return version_guardada


def resolver_version_para_inventario(
    db: Session,
    inventario: Inventario,
    codigo_formato: str,
    version_id: int | None = None,
) -> FormatoVersion | None:
    if version_id is not None:
        version = db.scalar(
            select(FormatoVersion)
            .join(FormatoImpresion)
            .where(
                FormatoVersion.id == version_id,
                FormatoImpresion.codigo == codigo_formato,
            )
            .options(selectinload(FormatoVersion.columnas))
        )
        if version:
            _cargar_estilos(db, [version])
        return version
    if (
        inventario.formato_version_id
        and codigo_formato == inventario.formato_impresion
    ):
        version = db.scalar(
            select(FormatoVersion)
            .where(FormatoVersion.id == inventario.formato_version_id)
            .options(selectinload(FormatoVersion.columnas))
        )
        if version:
            _cargar_estilos(db, [version])
        return version
    formato = obtener_formato(db, codigo_formato)
    return formato.versiones[-1] if formato and formato.versiones else None


def versiones_para_formato(
    db: Session,
    codigo_formato: str,
) -> list[FormatoVersion]:
    versiones = list(
        db.scalars(
            select(FormatoVersion)
            .join(FormatoImpresion)
            .where(FormatoImpresion.codigo == codigo_formato)
            .options(selectinload(FormatoVersion.columnas))
            .order_by(FormatoVersion.numero.desc())
        ).all()
    )
    _cargar_estilos(db, versiones)
    return versiones


def version_actual_id(db: Session, codigo: str) -> int | None:
    formato = obtener_formato(db, codigo)
    return formato.versiones[-1].id if formato and formato.versiones else None
