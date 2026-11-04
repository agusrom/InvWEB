from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from sqlalchemy import bindparam, text

from app.database import production_engine
from app.services.piece_provider import (
    normalizar_codigo,
    obtener_estructura_recursiva,
)


MOVIMIENTOS_DEBUG = os.getenv("MOVIMIENTOS_DEBUG", "0").strip().lower() not in {
    "0", "false", "no", "off",
}
MOVIMIENTOS_DEBUG_DETAIL = os.getenv(
    "MOVIMIENTOS_DEBUG_DETAIL", "0"
).strip().lower() not in {"0", "false", "no", "off"}
DEBUG_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "conciliacion_debug.log"


def _debug(mensaje: str) -> None:
    """Traza visible en la consola donde se ejecuta Uvicorn."""
    if MOVIMIENTOS_DEBUG:
        linea = f"[CONCILIACION DEBUG] {mensaje}"
        print(linea, flush=True)
        try:
            DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with DEBUG_LOG_PATH.open("a", encoding="utf-8") as archivo:
                archivo.write(linea + "\n")
        except OSError as error:
            print(
                f"[CONCILIACION DEBUG] No se pudo escribir el log: {error}",
                flush=True,
            )


@dataclass(frozen=True)
class CorteRemito:
    original: str
    numero: int


def normalizar_remito(valor: Any) -> CorteRemito:
    original = str(valor or "").strip()
    if not original:
        raise ValueError("Falta informar un número de remito")
    sufijo = original.rsplit("-", 1)[-1].strip()
    if not sufijo.isdigit():
        raise ValueError(f"El remito '{original}' no termina en un número válido")
    return CorteRemito(original=original, numero=int(sufijo))


def _fecha_texto(valor: Any) -> str:
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return str(valor or "").strip()


def _cantidad(valor: Any) -> float:
    return float(valor or 0)


def _fecha_corte(valor: date | datetime | str, nombre: str) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor or "").strip()[:10])
    except ValueError as error:
        raise ValueError(f"No se pudo determinar la {nombre}") from error


def _validar_intervalo_fechas(
    inicio: date | datetime | str,
    fin: date | datetime | str,
) -> tuple[date, date]:
    fecha_inicial = _fecha_corte(inicio, "fecha del inventario inicial")
    fecha_final = _fecha_corte(fin, "fecha del inventario final")
    if fecha_final < fecha_inicial:
        raise ValueError(
            "La fecha del inventario final no puede ser anterior a la inicial"
        )
    return fecha_inicial, fecha_final


def _validar_intervalo(inicio: str, fin: str, tipo: str) -> tuple[int, int]:
    corte_inicial = normalizar_remito(inicio)
    corte_final = normalizar_remito(fin)
    if corte_final.numero < corte_inicial.numero:
        raise ValueError(
            f"El remito final de {tipo} ({corte_final.original}) no puede ser "
            f"menor al inicial ({corte_inicial.original})"
        )
    return corte_inicial.numero, corte_final.numero


def _materiales_por_pieza(codigos_pieza: set[str]) -> dict[str, set[str]]:
    """Devuelve las piezas permitidas agrupadas por su MATE_ de produc01."""
    codigos = sorted({normalizar_codigo(codigo) for codigo in codigos_pieza})
    if not codigos:
        return {}
    if production_engine is None:
        materiales: dict[str, set[str]] = defaultdict(set)
        for codigo in codigos:
            # En modo demo la relación vive en el mismo maestro simulado.
            from app.services.piece_provider import DEMO_PIEZAS

            material = normalizar_codigo(
                DEMO_PIEZAS.get(codigo, {}).get("codigo_material", "")
            )
            if material:
                materiales[material].add(codigo)
        return dict(materiales)

    consulta = text(
        """
        SELECT
            TRIM(`GCOD_`) AS codigo_pieza,
            TRIM(COALESCE(`MATE_`, '')) AS codigo_material
        FROM `produc01`
        WHERE UPPER(TRIM(`GCOD_`)) IN :codigos
          AND TRIM(COALESCE(`MATE_`, '')) <> ''
        """
    ).bindparams(bindparam("codigos", expanding=True))
    with production_engine.connect() as conexion:
        filas = conexion.execute(
            consulta,
            {"codigos": codigos},
        ).mappings().all()

    materiales: dict[str, set[str]] = defaultdict(set)
    for fila in filas:
        codigo_pieza = normalizar_codigo(fila["codigo_pieza"])
        codigo_material = normalizar_codigo(fila["codigo_material"])
        if codigo_pieza and codigo_material:
            materiales[codigo_material].add(codigo_pieza)
    return dict(materiales)


def _filas_ingresos(
    inicio: str,
    fin: str,
    piezas_por_material: dict[str, set[str]],
) -> list[dict]:
    desde, hasta = _validar_intervalo(inicio, fin, "ingreso")
    materiales = sorted(piezas_por_material)
    if production_engine is None or not materiales:
        return []
    consulta = text(
        """
        SELECT
            TRIM(`CMAT_`) AS codigo,
            SUM(COALESCE(`CANT_`, 0)) AS cantidad,
            `FECH_` AS fecha,
            TRIM(CAST(`RMTO_` AS CHAR)) AS remito,
            CAST(TRIM(CAST(`RMTO_` AS CHAR)) AS UNSIGNED) AS remito_numero
        FROM `mtprim06`
        WHERE TRIM(`CODI_`) = 'RC'
          AND CAST(TRIM(CAST(`RMTO_` AS CHAR)) AS UNSIGNED) > :desde
          AND CAST(TRIM(CAST(`RMTO_` AS CHAR)) AS UNSIGNED) <= :hasta
          AND UPPER(TRIM(`CMAT_`)) IN :materiales
        GROUP BY
            TRIM(`CMAT_`), `FECH_`, TRIM(CAST(`RMTO_` AS CHAR)),
            CAST(TRIM(CAST(`RMTO_` AS CHAR)) AS UNSIGNED)
        ORDER BY remito_numero, `FECH_`, codigo
        """
    ).bindparams(bindparam("materiales", expanding=True))
    with production_engine.connect() as conexion:
        filas = conexion.execute(
            consulta,
            {"desde": desde, "hasta": hasta, "materiales": materiales},
        ).mappings().all()
    return [
        {
            "remito": str(fila["remito"] or "").strip(),
            "remito_numero": int(fila["remito_numero"] or 0),
            "fecha": _fecha_texto(fila["fecha"]),
            "codigo": normalizar_codigo(fila["codigo"]),
            "cantidad": _cantidad(fila["cantidad"]),
        }
        for fila in filas
    ]


def _filas_ingresos_por_fecha(
    fecha_inicial: date,
    fecha_final: date,
    piezas_por_material: dict[str, set[str]],
) -> list[dict]:
    materiales = sorted(piezas_por_material)
    if production_engine is None or not materiales:
        return []
    consulta = text(
        """
        SELECT
            TRIM(`CMAT_`) AS codigo,
            SUM(COALESCE(`CANT_`, 0)) AS cantidad,
            `FECH_` AS fecha,
            TRIM(CAST(`RMTO_` AS CHAR)) AS remito,
            CAST(TRIM(CAST(`RMTO_` AS CHAR)) AS UNSIGNED) AS remito_numero
        FROM `mtprim06`
        WHERE TRIM(`CODI_`) = 'RC'
          AND DATE(`FECH_`) > :fecha_inicial
          AND DATE(`FECH_`) <= :fecha_final
          AND UPPER(TRIM(`CMAT_`)) IN :materiales
        GROUP BY
            TRIM(`CMAT_`), `FECH_`, TRIM(CAST(`RMTO_` AS CHAR)),
            CAST(TRIM(CAST(`RMTO_` AS CHAR)) AS UNSIGNED)
        ORDER BY `FECH_`, remito_numero, codigo
        """
    ).bindparams(bindparam("materiales", expanding=True))
    with production_engine.connect() as conexion:
        filas = conexion.execute(
            consulta,
            {
                "fecha_inicial": fecha_inicial,
                "fecha_final": fecha_final,
                "materiales": materiales,
            },
        ).mappings().all()
    return [
        {
            "remito": str(fila["remito"] or "").strip(),
            "remito_numero": int(fila["remito_numero"] or 0),
            "fecha": _fecha_texto(fila["fecha"]),
            "codigo": normalizar_codigo(fila["codigo"]),
            "cantidad": _cantidad(fila["cantidad"]),
        }
        for fila in filas
    ]


def _fechas_cortes_ingreso(inicio: str, fin: str) -> dict[int, date | datetime]:
    desde = normalizar_remito(inicio).numero
    hasta = normalizar_remito(fin).numero
    if production_engine is None:
        return {}
    with production_engine.connect() as conexion:
        filas = conexion.execute(
            text(
                """
                SELECT
                    CAST(TRIM(CAST(`RMTO_` AS CHAR)) AS UNSIGNED) AS numero,
                    MAX(`FECH_`) AS fecha
                FROM `mtprim06`
                WHERE TRIM(`CODI_`) = 'RC'
                  AND CAST(TRIM(CAST(`RMTO_` AS CHAR)) AS UNSIGNED)
                        IN (:desde, :hasta)
                GROUP BY CAST(TRIM(CAST(`RMTO_` AS CHAR)) AS UNSIGNED)
                """
            ),
            {"desde": desde, "hasta": hasta},
        ).mappings().all()
    return {
        int(fila["numero"]): fila["fecha"]
        for fila in filas
        if fila["numero"] is not None and fila["fecha"] is not None
    }


def _filas_ingresos_con_limites(
    fecha_limite_inicial: date | datetime,
    fecha_limite_final: date | datetime,
    piezas_por_material: dict[str, set[str]],
) -> list[dict]:
    """Consulta por la cronologia ubicada mediante los documentos de corte."""
    materiales = sorted(piezas_por_material)
    if production_engine is None or not materiales:
        return []
    consulta = text(
        """
        SELECT
            TRIM(`CMAT_`) AS codigo,
            SUM(COALESCE(`CANT_`, 0)) AS cantidad,
            `FECH_` AS fecha,
            TRIM(CAST(`RMTO_` AS CHAR)) AS remito,
            CAST(TRIM(CAST(`RMTO_` AS CHAR)) AS UNSIGNED) AS remito_numero
        FROM `mtprim06`
        WHERE TRIM(`CODI_`) = 'RC'
          AND `FECH_` > :fecha_limite_inicial
          AND `FECH_` <= :fecha_limite_final
          AND UPPER(TRIM(`CMAT_`)) IN :materiales
        GROUP BY TRIM(`CMAT_`), `FECH_`, TRIM(CAST(`RMTO_` AS CHAR)),
                 CAST(TRIM(CAST(`RMTO_` AS CHAR)) AS UNSIGNED)
        ORDER BY `FECH_`, remito_numero, codigo
        """
    ).bindparams(bindparam("materiales", expanding=True))
    with production_engine.connect() as conexion:
        filas = conexion.execute(
            consulta,
            {
                "fecha_limite_inicial": fecha_limite_inicial,
                "fecha_limite_final": fecha_limite_final,
                "materiales": materiales,
            },
        ).mappings().all()
    return [
        {
            "remito": str(fila["remito"] or "").strip(),
            "remito_numero": int(fila["remito_numero"] or 0),
            "fecha": _fecha_texto(fila["fecha"]),
            "codigo": normalizar_codigo(fila["codigo"]),
            "cantidad": _cantidad(fila["cantidad"]),
        }
        for fila in filas
    ]


def _filas_egresos(
    inicio: str,
    fin: str,
    codigos_padre: set[str],
) -> list[dict]:
    desde, hasta = _validar_intervalo(inicio, fin, "egreso")
    padres = sorted({normalizar_codigo(codigo) for codigo in codigos_padre})
    if production_engine is None or not padres:
        return []
    consulta = text(
        """
        SELECT
            TRIM(`CDOC_`) AS remito,
            CAST(SUBSTRING_INDEX(TRIM(`CDOC_`), '-', -1) AS UNSIGNED)
                AS remito_numero,
            `FECH_` AS fecha,
            TRIM(`GCOD_`) AS codigo_pieza,
            SUM(COALESCE(`CANT_`, 0)) AS cantidad
        FROM `produc08`
        WHERE TRIM(`STAT_`) = 'D'
          AND CAST(SUBSTRING_INDEX(TRIM(`CDOC_`), '-', -1) AS UNSIGNED)
                > :desde
          AND CAST(SUBSTRING_INDEX(TRIM(`CDOC_`), '-', -1) AS UNSIGNED)
                <= :hasta
          AND UPPER(TRIM(`GCOD_`)) IN :padres
        GROUP BY
            TRIM(`CDOC_`), `FECH_`, TRIM(`GCOD_`),
            CAST(SUBSTRING_INDEX(TRIM(`CDOC_`), '-', -1) AS UNSIGNED)
        ORDER BY remito_numero, `FECH_`, codigo_pieza
        """
    ).bindparams(bindparam("padres", expanding=True))
    with production_engine.connect() as conexion:
        filas = conexion.execute(
            consulta,
            {"desde": desde, "hasta": hasta, "padres": padres},
        ).mappings().all()
    return [
        {
            "remito": str(fila["remito"] or "").strip(),
            "remito_numero": int(fila["remito_numero"] or 0),
            "fecha": _fecha_texto(fila["fecha"]),
            "codigo_pieza": normalizar_codigo(fila["codigo_pieza"]),
            "cantidad": _cantidad(fila["cantidad"]),
        }
        for fila in filas
    ]


def _filas_egresos_por_fecha(
    fecha_inicial: date,
    fecha_final: date,
    codigos_padre: set[str],
) -> list[dict]:
    padres = sorted({normalizar_codigo(codigo) for codigo in codigos_padre})
    if production_engine is None or not padres:
        return []
    consulta = text(
        """
        SELECT
            TRIM(`CDOC_`) AS remito,
            CAST(SUBSTRING_INDEX(TRIM(`CDOC_`), '-', -1) AS UNSIGNED)
                AS remito_numero,
            `FECH_` AS fecha,
            TRIM(`GCOD_`) AS codigo_pieza,
            SUM(COALESCE(`CANT_`, 0)) AS cantidad
        FROM `produc08`
        WHERE TRIM(`STAT_`) = 'D'
          AND DATE(`FECH_`) > :fecha_inicial
          AND DATE(`FECH_`) <= :fecha_final
          AND UPPER(TRIM(`GCOD_`)) IN :padres
        GROUP BY
            TRIM(`CDOC_`), `FECH_`, TRIM(`GCOD_`),
            CAST(SUBSTRING_INDEX(TRIM(`CDOC_`), '-', -1) AS UNSIGNED)
        ORDER BY `FECH_`, remito_numero, codigo_pieza
        """
    ).bindparams(bindparam("padres", expanding=True))
    with production_engine.connect() as conexion:
        filas = conexion.execute(
            consulta,
            {
                "fecha_inicial": fecha_inicial,
                "fecha_final": fecha_final,
                "padres": padres,
            },
        ).mappings().all()
    return [
        {
            "remito": str(fila["remito"] or "").strip(),
            "remito_numero": int(fila["remito_numero"] or 0),
            "fecha": _fecha_texto(fila["fecha"]),
            "codigo_pieza": normalizar_codigo(fila["codigo_pieza"]),
            "cantidad": _cantidad(fila["cantidad"]),
        }
        for fila in filas
    ]


def _fechas_cortes_egreso(inicio: str, fin: str) -> dict[int, date | datetime]:
    desde = normalizar_remito(inicio).numero
    hasta = normalizar_remito(fin).numero
    if production_engine is None:
        return {}
    with production_engine.connect() as conexion:
        filas = conexion.execute(
            text(
                """
                SELECT
                    CAST(SUBSTRING_INDEX(TRIM(`CDOC_`), '-', -1) AS UNSIGNED)
                        AS numero,
                    MAX(`FECH_`) AS fecha
                FROM `produc08`
                WHERE TRIM(`STAT_`) = 'D'
                  AND CAST(
                        SUBSTRING_INDEX(TRIM(`CDOC_`), '-', -1) AS UNSIGNED
                      ) IN (:desde, :hasta)
                GROUP BY CAST(
                    SUBSTRING_INDEX(TRIM(`CDOC_`), '-', -1) AS UNSIGNED
                )
                """
            ),
            {"desde": desde, "hasta": hasta},
        ).mappings().all()
    return {
        int(fila["numero"]): fila["fecha"]
        for fila in filas
        if fila["numero"] is not None and fila["fecha"] is not None
    }


def _filas_egresos_con_limites(
    fecha_limite_inicial: date | datetime,
    fecha_limite_final: date | datetime,
    codigos_origen: set[str],
) -> list[dict]:
    codigos = sorted({normalizar_codigo(codigo) for codigo in codigos_origen})
    if production_engine is None or not codigos:
        _debug(
            "No se consultó produc08: no hay conexión productiva o la lista "
            "de códigos válidos está vacía."
        )
        return []
    expresion_remito = (
        "CAST(SUBSTRING_INDEX(TRIM(`CDOC_`), '-', -1) AS UNSIGNED)"
    )
    consulta = text(
        f"""
        SELECT
            TRIM(`CDOC_`) AS remito,
            {expresion_remito} AS remito_numero,
            `FECH_` AS fecha,
            TRIM(`GCOD_`) AS codigo_pieza,
            SUM(COALESCE(`CANT_`, 0)) AS cantidad,
            MAX(COALESCE(`LACTIVO_`, 0)) AS activo,
            'D' AS estado
        FROM `produc08`
        WHERE `FECH_` > :fecha_limite_inicial
          AND `FECH_` <= :fecha_limite_final
          AND UPPER(TRIM(COALESCE(`STAT_`, ''))) = 'D'
          AND UPPER(TRIM(`GCOD_`)) IN :codigos
        GROUP BY
            TRIM(`CDOC_`), {expresion_remito}, `FECH_`, TRIM(`GCOD_`)
        ORDER BY `FECH_`, remito_numero, codigo_pieza
        """
    ).bindparams(bindparam("codigos", expanding=True))
    _debug(
        "Consultando produc08 con filtro de estado y códigos en MySQL. "
        f"Intervalo: FECH_ > {fecha_limite_inicial!s} y "
        f"FECH_ <= {fecha_limite_final!s}."
    )
    _debug(
        f"Códigos admitidos por estructura ({len(codigos)}): "
        + ", ".join(codigos)
    )
    with production_engine.connect() as conexion:
        filas = conexion.execute(
            consulta,
            {
                "fecha_limite_inicial": fecha_limite_inicial,
                "fecha_limite_final": fecha_limite_final,
                "codigos": codigos,
            },
        ).mappings().all()
    _debug(
        f"produc08 devolvió {len(filas)} movimientos ya filtrados y agrupados."
    )

    agrupadas: dict[tuple, dict] = {}
    codigos_validos = set(codigos)
    incluidas = 0
    for indice, fila in enumerate(filas, start=1):
        codigo_crudo = str(fila["codigo_pieza"] or "")
        codigo = normalizar_codigo(codigo_crudo)
        remito = str(fila["remito"] or "").strip()
        activo = int(fila["activo"] or 0)
        estado = str(fila["estado"] or "").strip().upper()
        motivos = []
        if estado != "D":
            motivos.append(f"STAT_={estado or '(vacío)'}")
        if codigo not in codigos_validos:
            motivos.append("GCOD_ no pertenece a las estructuras admitidas")

        if motivos:
            if MOVIMIENTOS_DEBUG_DETAIL:
                _debug(
                    f"Fila {indice} DESCARTADA | remito={remito!r} | "
                    f"fecha={_fecha_texto(fila['fecha'])} | "
                    f"GCOD_ crudo={codigo_crudo!r} | normalizado={codigo!r} | "
                    f"cantidad={_cantidad(fila['cantidad'])} | "
                    f"LACTIVO_={activo} (informativo) | motivo: "
                    + "; ".join(motivos)
                )
            continue

        clave = (
            remito,
            int(fila["remito_numero"] or 0),
            _fecha_texto(fila["fecha"]),
            codigo,
        )
        if clave not in agrupadas:
            agrupadas[clave] = {
                "remito": remito,
                "remito_numero": int(fila["remito_numero"] or 0),
                "fecha": _fecha_texto(fila["fecha"]),
                "codigo_pieza": codigo,
                "cantidad": 0.0,
            }
        agrupadas[clave]["cantidad"] += _cantidad(fila["cantidad"])
        incluidas += 1
        if MOVIMIENTOS_DEBUG_DETAIL:
            _debug(
                f"Fila {indice} INCLUIDA | remito={remito!r} | "
                f"fecha={_fecha_texto(fila['fecha'])} | GCOD_={codigo!r} | "
                f"cantidad={_cantidad(fila['cantidad'])} | "
                f"LACTIVO_={activo} (informativo)"
            )

    resultado = sorted(
        agrupadas.values(),
        key=lambda fila: (
            fila["fecha"], fila["remito_numero"], fila["remito"],
            fila["codigo_pieza"],
        ),
    )
    _debug(
        f"Filtro Python: {incluidas} filas incluidas, "
        f"{len(filas) - incluidas} descartadas, "
        f"{len(resultado)} movimientos agrupados."
    )
    return resultado


def _estructura_cacheada(codigo_pieza: str, cache: dict[str, list]) -> list:
    codigo = normalizar_codigo(codigo_pieza)
    if codigo not in cache:
        cache[codigo] = obtener_estructura_recursiva(codigo)
    return cache[codigo]


def _componentes_terminales(
    codigo_pieza: str,
    cache_estructuras: dict[str, list],
) -> list[dict]:
    nodos = _estructura_cacheada(codigo_pieza, cache_estructuras)
    codigos_con_hijos = {
        nodo.codigo_padre
        for nodo in nodos
        if nodo.codigo_padre
    }
    terminales = [
        nodo for nodo in nodos if nodo.codigo not in codigos_con_hijos
    ]
    return [
        {
            "codigo": normalizar_codigo(nodo.codigo),
            "uso": float(nodo.uso_acumulado),
        }
        for nodo in terminales
    ]


def _codigos_estructura(
    codigos_padre: set[str],
    cache_estructuras: dict[str, list],
) -> set[str]:
    """Incluye padres, subconjuntos y componentes que pueden salir en produc08."""
    codigos = {
        normalizar_codigo(codigo)
        for codigo in codigos_padre
        if normalizar_codigo(codigo)
    }
    for codigo_padre in list(codigos):
        nodos = _estructura_cacheada(codigo_padre, cache_estructuras)
        _debug(
            f"Estructura de padre {codigo_padre!r}: {len(nodos)} nodos -> "
            + ", ".join(
                f"{normalizar_codigo(nodo.codigo)}(uso={nodo.uso_acumulado})"
                for nodo in nodos
            )
        )
        for nodo in nodos:
            codigo = normalizar_codigo(nodo.codigo)
            if codigo:
                codigos.add(codigo)
    return codigos


def calcular_movimientos(
    remito_ingreso_inicial: str,
    remito_ingreso_final: str,
    remito_egreso_inicial: str,
    remito_egreso_final: str,
    fecha_inicial: date | datetime | str,
    fecha_final: date | datetime | str,
    codigos_padre: set[str] | None = None,
    codigos_resultado: set[str] | None = None,
) -> dict:
    inicio_calculo = perf_counter()
    _debug("=" * 72)
    _debug(
        f"INICIO DE RECÁLCULO {datetime.now().isoformat(timespec='seconds')} | "
        f"inventarios: {fecha_inicial!s} -> {fecha_final!s}"
    )
    fecha_desde, fecha_hasta = _validar_intervalo_fechas(
        fecha_inicial,
        fecha_final,
    )
    padres_permitidos = {
        normalizar_codigo(codigo) for codigo in (codigos_padre or set())
    }
    resultados_permitidos = {
        normalizar_codigo(codigo) for codigo in (codigos_resultado or set())
    }
    piezas_por_material = _materiales_por_pieza(resultados_permitidos)
    advertencias = []
    criterios = {}

    def resolver_cortes(
        tipo: str,
        inicio: str,
        fin: str,
        buscar_existentes,
    ) -> tuple[date | datetime, date | datetime, bool, bool]:
        try:
            corte_inicial = normalizar_remito(inicio)
            corte_final = normalizar_remito(fin)
            _debug(
                f"Buscando cortes de {tipo}: inicial={corte_inicial.original!r} "
                f"(número {corte_inicial.numero}), final={corte_final.original!r} "
                f"(número {corte_final.numero})."
            )
            fechas_corte = buscar_existentes(inicio, fin)
        except ValueError as error:
            advertencias.append(
                f"No se pudo usar el corte de {tipo} por remitos: {error}."
            )
            return fecha_desde, fecha_hasta, False, False
        inicial_encontrado = corte_inicial.numero in fechas_corte
        final_encontrado = corte_final.numero in fechas_corte
        _debug(
            f"Resultado cortes de {tipo}: inicial="
            f"{fechas_corte.get(corte_inicial.numero, 'NO ENCONTRADO')}, final="
            f"{fechas_corte.get(corte_final.numero, 'NO ENCONTRADO')}."
        )
        if not inicial_encontrado:
            advertencias.append(
                f"No se encontró el remito {tipo} inicial "
                f"{corte_inicial.original}; ese extremo se cortó por la "
                f"fecha {fecha_desde.isoformat()} (excluida)."
            )
        if not final_encontrado:
            advertencias.append(
                f"No se encontró el remito {tipo} final "
                f"{corte_final.original}; ese extremo se cortó por la "
                f"fecha {fecha_hasta.isoformat()} (incluida)."
            )
        return (
            fechas_corte.get(corte_inicial.numero, fecha_desde),
            fechas_corte.get(corte_final.numero, fecha_hasta),
            inicial_encontrado,
            final_encontrado,
        )

    def nombre_criterio(inicial_por_remito: bool, final_por_remito: bool) -> str:
        if inicial_por_remito and final_por_remito:
            return "REMITOS"
        if not inicial_por_remito and not final_por_remito:
            return "FECHAS"
        if inicial_por_remito:
            return "MIXTO_INICIAL_REMITO"
        return "MIXTO_FINAL_REMITO"

    ingreso_fecha_desde, ingreso_fecha_hasta, ingreso_inicio_remito, ingreso_fin_remito = resolver_cortes(
        "ingreso",
        remito_ingreso_inicial,
        remito_ingreso_final,
        _fechas_cortes_ingreso,
    )
    if ingreso_fecha_hasta < ingreso_fecha_desde:
        raise ValueError(
            "El remito final de ingreso aparece antes que el remito inicial "
            "segun FECH_."
        )
    ingresos = _filas_ingresos_con_limites(
        ingreso_fecha_desde,
        ingreso_fecha_hasta,
        piezas_por_material,
    )
    criterios["ingreso"] = nombre_criterio(
        ingreso_inicio_remito,
        ingreso_fin_remito,
    )
    if criterios["ingreso"] == "FECHAS":
        advertencias.append(
            "Los ingresos se calcularon de forma aproximada por fecha: "
            f"después del {fecha_desde.isoformat()} y hasta el "
            f"{fecha_hasta.isoformat()}, inclusive."
        )

    egreso_fecha_desde, egreso_fecha_hasta, egreso_inicio_remito, egreso_fin_remito = resolver_cortes(
        "egreso",
        remito_egreso_inicial,
        remito_egreso_final,
        _fechas_cortes_egreso,
    )
    if egreso_fecha_hasta < egreso_fecha_desde:
        raise ValueError(
            "El remito final de egreso aparece antes que el remito inicial "
            "segun FECH_."
        )
    # produc08 puede contener el padre, un subconjunto o un componente devuelto
    # por separado. Se admiten todos los códigos pertenecientes a la estructura
    # de los padres comunes, pero el resultado final sigue limitado a los
    # renglones comparables de la conciliación.
    cache_estructuras: dict[str, list] = {}
    codigos_egreso = _codigos_estructura(
        padres_permitidos,
        cache_estructuras,
    )
    egresos = _filas_egresos_con_limites(
        egreso_fecha_desde,
        egreso_fecha_hasta,
        codigos_egreso,
    )
    criterios["egreso"] = nombre_criterio(
        egreso_inicio_remito,
        egreso_fin_remito,
    )
    if criterios["egreso"] == "FECHAS":
        advertencias.append(
            "Los egresos se calcularon de forma aproximada por fecha: "
            f"después del {fecha_desde.isoformat()} y hasta el "
            f"{fecha_hasta.isoformat()}, inclusive."
        )

    ingresos_por_codigo: dict[str, float] = defaultdict(float)
    detalles_ingreso: dict[str, list[dict]] = defaultdict(list)
    ingresos_auditados = []
    for fila in ingresos:
        codigo_material = fila["codigo"]
        for codigo_pieza in sorted(
            piezas_por_material.get(codigo_material, set())
        ):
            if codigo_pieza not in resultados_permitidos:
                continue
            detalle = dict(fila)
            detalle["codigo_material"] = codigo_material
            detalle["codigo"] = codigo_pieza
            detalle["movimiento_clave"] = (
                f"AUTO|{fila['remito']}|{fila['fecha']}|"
                f"{codigo_material}|{codigo_pieza}"
            )
            ingresos_por_codigo[codigo_pieza] += fila["cantidad"]
            detalles_ingreso[codigo_pieza].append(detalle)
            ingresos_auditados.append(detalle)

    egresos_por_codigo: dict[str, float] = defaultdict(float)
    detalles_egreso: dict[str, list[dict]] = defaultdict(list)
    estructuras: dict[str, list[dict]] = {}
    for fila in egresos:
        codigo_pieza = fila["codigo_pieza"]
        _debug(
            f"Procesando egreso aceptado: remito={fila['remito']!r}, "
            f"GCOD_={codigo_pieza!r}, cantidad={fila['cantidad']}."
        )
        fila["movimiento_clave"] = (
            f"AUTO|{fila['remito']}|{fila['fecha']}|{codigo_pieza}"
        )
        origen_componente = codigo_pieza not in padres_permitidos
        if codigo_pieza in resultados_permitidos:
            estructuras[codigo_pieza] = [{"codigo": codigo_pieza, "uso": 1.0}]
            _debug(
                f"{codigo_pieza!r} coincide directamente con un renglón de "
                "la conciliación: se aplica uso 1."
            )
        elif codigo_pieza not in estructuras:
            estructuras[codigo_pieza] = _componentes_terminales(
                codigo_pieza,
                cache_estructuras,
            )
            _debug(
                f"{codigo_pieza!r} se trata como padre/subconjunto. "
                f"Terminales encontrados: {estructuras[codigo_pieza]!r}."
            )
        componentes = []
        for componente in estructuras[codigo_pieza]:
            codigo = componente["codigo"]
            if codigo not in resultados_permitidos:
                _debug(
                    f"Componente resultante {codigo!r} descartado porque no "
                    "existe como renglón comparable en ambos inventarios."
                )
                continue
            equivalente = fila["cantidad"] * componente["uso"]
            _debug(
                f"SUMA: origen={codigo_pieza!r} -> componente={codigo!r}; "
                f"{fila['cantidad']} x uso {componente['uso']} = {equivalente}."
            )
            detalle = {
                "remito": fila["remito"],
                "remito_numero": fila["remito_numero"],
                "fecha": fila["fecha"],
                "pieza_origen": codigo_pieza,
                "cantidad_pieza": fila["cantidad"],
                "uso": componente["uso"],
                "cantidad_equivalente": equivalente,
                "despacho_directo": origen_componente,
            }
            egresos_por_codigo[codigo] += equivalente
            detalles_egreso[codigo].append(detalle)
            componentes.append({
                "codigo": codigo,
                "uso": componente["uso"],
                "cantidad_equivalente": equivalente,
                "despacho_directo": origen_componente,
            })
        fila["componentes"] = componentes
        if not componentes:
            _debug(
                f"ATENCIÓN: el egreso {codigo_pieza!r} fue aceptado desde "
                "produc08 pero no terminó sumando a ningún renglón."
            )

    _debug(
        "Totales finales de egresos por código: "
        + repr(dict(egresos_por_codigo))
    )
    _debug(
        f"FIN DE RECÁLCULO en {perf_counter() - inicio_calculo:.2f}s | "
        f"ingresos={len(ingresos_auditados)}, egresos={len(egresos)}."
    )

    return {
        "ingresos": ingresos_auditados,
        "egresos": egresos,
        "ingresos_por_codigo": dict(ingresos_por_codigo),
        "egresos_por_codigo": dict(egresos_por_codigo),
        "detalles_ingreso": dict(detalles_ingreso),
        "detalles_egreso": dict(detalles_egreso),
        "advertencias": advertencias,
        "criterio_ingreso": criterios["ingreso"],
        "criterio_egreso": criterios["egreso"],
    }
