from dataclasses import asdict, dataclass
import logging
from time import perf_counter

from sqlalchemy import bindparam, text

from app.database import production_engine


logger = logging.getLogger("uvicorn.error")


@dataclass
class OperacionPieza:
    operacion: str
    titulo: str
    stock: float
    proveedores: str = ""


@dataclass
class LoteMaterial:
    lote: str
    stock: float


@dataclass
class MaterialProductivo:
    codigo: str
    descripcion: str
    diametro: str
    largo: str
    espesor: str
    unidad: str
    stock_total: float
    lotes: list[LoteMaterial]
    fuente: str

    def to_dict(self) -> dict:
        datos = asdict(self)
        datos["lotes"] = [asdict(lote) for lote in self.lotes]
        return datos


@dataclass
class NodoEstructura:
    codigo: str
    codigo_padre: str
    uso_directo: float
    uso_acumulado: float
    nivel: int
    ruta: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PiezaProductiva:
    codigo: str
    codigo_cliente: str
    codigo_material: str
    descripcion: str
    stock_terminado: float
    stock_proceso_total: float
    proveedores_proceso: str
    operaciones: list[OperacionPieza]
    fuente: str
    tiene_operaciones_maestro: bool = True
    stock_material: float = 0
    lotes_material: list[LoteMaterial] | None = None
    tipo_estructura: str = "INDEPENDIENTE"
    consumo_material: float = 1
    unidad_consumo: str = "C/U"
    descripcion_material: str = ""
    unidad_material: str = ""

    def to_dict(self) -> dict:
        datos = asdict(self)
        datos["operaciones"] = [
            asdict(operacion)
            for operacion in self.operaciones
        ]
        datos["lotes_material"] = [
            asdict(lote)
            for lote in (self.lotes_material or [])
        ]
        return datos


DEMO_PIEZAS = {
    "AN-1042": {
        "codigo_cliente": "CLI-AN-1042",
        "codigo_material": "MP-ACERO-01",
        "descripcion": "Soporte lateral",
        "stock_terminado": 126,
        "operaciones": [
            ("10", "Corte", 18, ""),
            ("20", "Estampado", 12, ""),
            ("30", "Pintura", 6, "104"),
        ],
    },
    "AN-2088": {
        "codigo_cliente": "CLI-AN-2088",
        "codigo_material": "MP-ACERO-02",
        "descripcion": "Refuerzo central",
        "stock_terminado": 84,
        "operaciones": [
            ("10", "Corte", 15, ""),
            ("20", "Plegado", 8, ""),
            ("30", "Soldadura", 5, ""),
        ],
    },
    "AN-3110": {
        "codigo_cliente": "CLI-AN-3110",
        "codigo_material": "MP-ACERO-03",
        "descripcion": "Conjunto bisagra",
        "stock_terminado": 52,
        "operaciones": [
            ("10", "Mecanizado", 9, ""),
            ("20", "Armado", 4, ""),
        ],
    },
    "MS-4401": {
        "codigo_cliente": "CLI-MS-4401",
        "codigo_material": "MP-CHAPA-01",
        "descripcion": "Placa estampada",
        "stock_terminado": 230,
        "operaciones": [
            ("10", "Corte", 22, ""),
            ("20", "Estampado", 14, ""),
        ],
    },
    "MS-4475": {
        "codigo_cliente": "CLI-MS-4475",
        "codigo_material": "MP-PERFIL-01",
        "descripcion": "Perfil mecanizado",
        "stock_terminado": 96,
        "operaciones": [
            ("10", "Corte", 16, ""),
            ("20", "Mecanizado", 7, "202"),
        ],
    },
    "MS-5520": {
        "codigo_cliente": "CLI-MS-5520",
        "codigo_material": "MP-ACERO-04",
        "descripcion": "Conjunto soldado",
        "stock_terminado": 41,
        "operaciones": [
            ("10", "Soldadura", 11, ""),
            ("20", "Pintura", 3, "104"),
        ],
    },
    "CD-0127": {
        "codigo_cliente": "CLI-CD-0127",
        "codigo_material": "MP-ACERO-05",
        "descripcion": "Brida de fijación",
        "stock_terminado": 74,
        "operaciones": [("10", "Estampado", 10, "")],
    },
    "CD-0184": {
        "codigo_cliente": "CLI-CD-0184",
        "codigo_material": "MP-PLAST-01",
        "descripcion": "Tapa protectora",
        "stock_terminado": 118,
        "operaciones": [("10", "Inyección", 20, "")],
    },
    "CD-0202": {
        "codigo_cliente": "CLI-CD-0202",
        "codigo_material": "MP-ACERO-06",
        "descripcion": "Soporte superior",
        "stock_terminado": 63,
        "operaciones": [
            ("10", "Corte", 12, ""),
            ("20", "Plegado", 7, ""),
        ],
    },
}

DEMO_MATERIALES = {
    "MP-ACERO-01": {
        "descripcion": "Chapa de acero laminada",
        "diametro": "",
        "largo": "2000",
        "espesor": "2",
        "unidad": "KGS",
        "lotes": [("DEMO-A", 30), ("DEMO-B", 18)],
    },
    "MP-ACERO-02": {
        "descripcion": "Fleje de acero",
        "diametro": "",
        "largo": "1500",
        "espesor": "1.5",
        "unidad": "KGS",
        "lotes": [("DEMO-C", 24)],
    },
    "MP-CHAPA-01": {
        "descripcion": "Chapa galvanizada",
        "diametro": "",
        "largo": "2500",
        "espesor": "1.2",
        "unidad": "KGS",
        "lotes": [],
    },
}

DEMO_ESTRUCTURA = {
    "AN-1042": [
        ("AN-2088", 2),
        ("MP-CHAPA-01", 1.5),
    ],
    "AN-2088": [
        ("MP-ACERO-02", 0.75),
    ],
}


def normalizar_codigo(codigo: str) -> str:
    return str(codigo or "").strip().upper()


def resolver_tipo_estructura(es_padre: bool, es_hijo: bool) -> str:
    if es_padre and es_hijo:
        return "SUBCONJUNTO"
    if es_padre:
        return "PADRE"
    if es_hijo:
        return "HIJO"
    return "INDEPENDIENTE"


def tipo_estructura_demo(codigo: str) -> str:
    padres = set(DEMO_ESTRUCTURA)
    hijos = {
        hijo
        for componentes in DEMO_ESTRUCTURA.values()
        for hijo, _uso in componentes
    }
    return resolver_tipo_estructura(codigo in padres, codigo in hijos)


def fuente_stock_actual() -> str:
    return "DEMO" if production_engine is None else "BASE_PRODUCTIVA"


def buscar_codigos_cliente_piezas(codigos) -> dict[str, str]:
    """Obtiene CCOD_ para varios códigos con una consulta por bloque.

    Los códigos que sean materias primas o no existan en produc01 se devuelven
    sin equivalencia y quedan en blanco en los reportes.
    """
    normalizados = sorted({normalizar_codigo(codigo) for codigo in codigos if normalizar_codigo(codigo)})
    if not normalizados:
        return {}
    if production_engine is None:
        return {
            codigo: str(DEMO_PIEZAS.get(codigo, {}).get("codigo_cliente", ""))
            for codigo in normalizados
        }
    statement = text(
        """
        SELECT
            TRIM(`GCOD_`) AS codigo,
            TRIM(COALESCE(`CCOD_`, '')) AS codigo_cliente
        FROM `produc01`
        WHERE TRIM(`GCOD_`) IN :codigos
        """
    ).bindparams(bindparam("codigos", expanding=True))
    result = {}
    with production_engine.connect() as conexion:
        for start in range(0, len(normalizados), 500):
            rows = conexion.execute(
                statement,
                {"codigos": normalizados[start:start + 500]},
            ).mappings().all()
            result.update({
                normalizar_codigo(row["codigo"]): str(row["codigo_cliente"] or "").strip()
                for row in rows
            })
    return result


def buscar_sugerencias_piezas(
    termino: str,
    limite: int = 10,
) -> list[dict]:
    termino = normalizar_codigo(termino)
    limite = max(1, min(int(limite), 20))
    if len(termino) < 2:
        return []

    if production_engine is None:
        resultados = []
        for codigo, datos in DEMO_PIEZAS.items():
            campos = (
                codigo,
                datos["codigo_cliente"],
                datos["descripcion"],
            )
            if any(termino in normalizar_codigo(campo) for campo in campos):
                resultados.append(
                    {
                        "codigo": codigo,
                        "codigo_cliente": datos["codigo_cliente"],
                        "descripcion": datos["descripcion"],
                        "codigo_material": datos["codigo_material"],
                    }
                )
        resultados.sort(
            key=lambda item: (
                not item["codigo"].startswith(termino),
                not item["codigo_cliente"].startswith(termino),
                item["codigo"],
            )
        )
        return resultados[:limite]

    patron = f"%{termino}%"
    prefijo = f"{termino}%"
    with production_engine.connect() as conexion:
        filas = conexion.execute(
            text(
                f"""
                SELECT
                    TRIM(`GCOD_`) AS codigo,
                    TRIM(COALESCE(`CCOD_`, '')) AS codigo_cliente,
                    TRIM(COALESCE(`DESC_`, '')) AS descripcion,
                    TRIM(COALESCE(`MATE_`, '')) AS codigo_material
                FROM `produc01`
                WHERE UPPER(TRIM(`GCOD_`)) LIKE :patron
                   OR UPPER(TRIM(COALESCE(`CCOD_`, ''))) LIKE :patron
                   OR UPPER(TRIM(COALESCE(`DESC_`, ''))) LIKE :patron
                ORDER BY
                    CASE
                        WHEN UPPER(TRIM(`GCOD_`)) LIKE :prefijo THEN 0
                        WHEN UPPER(TRIM(COALESCE(`CCOD_`, ''))) LIKE :prefijo THEN 1
                        ELSE 2
                    END,
                    `GCOD_`
                LIMIT {limite}
                """
            ),
            {"patron": patron, "prefijo": prefijo},
        ).mappings().all()
    return [
        {
            "codigo": str(fila["codigo"] or ""),
            "codigo_cliente": str(fila["codigo_cliente"] or ""),
            "descripcion": str(fila["descripcion"] or ""),
            "codigo_material": str(fila["codigo_material"] or ""),
        }
        for fila in filas
    ]


def buscar_sugerencias_materiales(
    termino: str,
    limite: int = 10,
) -> list[dict]:
    termino = normalizar_codigo(termino)
    limite = max(1, min(int(limite), 20))
    if len(termino) < 2:
        return []

    if production_engine is None:
        resultados = []
        for codigo, datos in DEMO_MATERIALES.items():
            if (
                termino in codigo
                or termino in normalizar_codigo(datos["descripcion"])
            ):
                resultados.append(
                    {
                        "codigo": codigo,
                        "descripcion": datos["descripcion"],
                        "unidad": datos["unidad"],
                        "diametro": datos["diametro"],
                        "largo": datos["largo"],
                        "espesor": datos["espesor"],
                    }
                )
        resultados.sort(
            key=lambda item: (
                not item["codigo"].startswith(termino),
                item["codigo"],
            )
        )
        return resultados[:limite]

    patron = f"%{termino}%"
    prefijo = f"{termino}%"
    with production_engine.connect() as conexion:
        filas = conexion.execute(
            text(
                f"""
                SELECT
                    TRIM(`CODGO_`) AS codigo,
                    TRIM(COALESCE(`DESCR_`, '')) AS descripcion,
                    TRIM(COALESCE(`UNDAD_`, '')) AS unidad,
                    TRIM(COALESCE(CAST(`DIAMT_` AS CHAR), '')) AS diametro,
                    TRIM(COALESCE(CAST(`LARGO_` AS CHAR), '')) AS largo,
                    TRIM(COALESCE(CAST(`ESPES_` AS CHAR), '')) AS espesor
                FROM `mtprim01`
                WHERE UPPER(TRIM(`CODGO_`)) LIKE :patron
                   OR UPPER(TRIM(COALESCE(`DESCR_`, ''))) LIKE :patron
                ORDER BY
                    CASE
                        WHEN UPPER(TRIM(`CODGO_`)) LIKE :prefijo THEN 0
                        ELSE 1
                    END,
                    `CODGO_`
                LIMIT {limite}
                """
            ),
            {"patron": patron, "prefijo": prefijo},
        ).mappings().all()
    return [
        {
            "codigo": str(fila["codigo"] or ""),
            "descripcion": str(fila["descripcion"] or ""),
            "unidad": str(fila["unidad"] or ""),
            "diametro": str(fila["diametro"] or ""),
            "largo": str(fila["largo"] or ""),
            "espesor": str(fila["espesor"] or ""),
        }
        for fila in filas
    ]


def buscar_pieza(codigo: str) -> PiezaProductiva | None:
    codigo = normalizar_codigo(codigo)
    if not codigo:
        return None
    if production_engine is None:
        return _buscar_demo(codigo)
    return _buscar_mysql(codigo)


def buscar_material(codigo: str) -> MaterialProductivo | None:
    codigo = normalizar_codigo(codigo)
    if not codigo:
        return None
    if production_engine is None:
        return _buscar_material_demo(codigo)
    return _buscar_material_mysql(codigo)


def obtener_estructura_recursiva(
    codigo_raiz: str,
    max_niveles: int = 20,
) -> list[NodoEstructura]:
    codigo_raiz = normalizar_codigo(codigo_raiz)
    if not codigo_raiz:
        return []
    if production_engine is None:
        return _recorrer_estructura(
            codigo_raiz,
            lambda padre: DEMO_ESTRUCTURA.get(padre, []),
            max_niveles,
        )

    inicio = perf_counter()
    cache_hijos: dict[str, list[tuple[str, float]]] = {}
    with production_engine.connect() as conexion:
        def obtener_hijos(padre: str) -> list[tuple[str, float]]:
            if padre not in cache_hijos:
                filas = conexion.execute(
                    text(
                        """
                        SELECT
                            TRIM(`GCOD_`) AS codigo,
                            COALESCE(`QXUN_`, 0) AS uso
                        FROM `produc10`
                        WHERE `VCOD_` = :padre
                        ORDER BY `GCOD_`
                        """
                    ),
                    {"padre": padre},
                ).mappings().all()
                cache_hijos[padre] = [
                    (
                        normalizar_codigo(fila["codigo"]),
                        float(fila["uso"] or 0),
                    )
                    for fila in filas
                    if normalizar_codigo(fila["codigo"])
                ]
            return cache_hijos[padre]

        nodos = _recorrer_estructura(
            codigo_raiz,
            obtener_hijos,
            max_niveles,
        )

    logger.info(
        "Estructura %s: %s códigos en %.2f s",
        codigo_raiz,
        len(nodos),
        perf_counter() - inicio,
    )
    return nodos


def _recorrer_estructura(
    codigo_raiz: str,
    obtener_hijos,
    max_niveles: int,
) -> list[NodoEstructura]:
    pendientes = [
        NodoEstructura(
            codigo=codigo_raiz,
            codigo_padre="",
            uso_directo=1,
            uso_acumulado=1,
            nivel=0,
            ruta=codigo_raiz,
        )
    ]
    recorridos: list[NodoEstructura] = []
    indice = 0

    while indice < len(pendientes):
        actual = pendientes[indice]
        indice += 1
        recorridos.append(actual)

        hijos = obtener_hijos(actual.codigo)
        if hijos and actual.nivel >= max_niveles:
            raise RuntimeError(
                f"La estructura supera el máximo de {max_niveles} niveles"
            )

        ruta_codigos = set(actual.ruta.split(" > "))
        for codigo_hijo, uso_directo in hijos:
            if codigo_hijo in ruta_codigos:
                logger.warning(
                    "Ciclo omitido en produc10: %s > %s",
                    actual.ruta,
                    codigo_hijo,
                )
                continue
            if len(pendientes) >= 5000:
                raise RuntimeError(
                    "La estructura supera el límite de 5000 relaciones"
                )
            pendientes.append(
                NodoEstructura(
                    codigo=codigo_hijo,
                    codigo_padre=actual.codigo,
                    uso_directo=uso_directo,
                    uso_acumulado=actual.uso_acumulado * uso_directo,
                    nivel=actual.nivel + 1,
                    ruta=f"{actual.ruta} > {codigo_hijo}",
                )
            )

    agregados: dict[str, NodoEstructura] = {}
    for nodo in recorridos:
        existente = agregados.get(nodo.codigo)
        if existente is None:
            agregados[nodo.codigo] = nodo
        else:
            existente.uso_acumulado += nodo.uso_acumulado
            if nodo.nivel < existente.nivel:
                existente.nivel = nodo.nivel
                existente.codigo_padre = nodo.codigo_padre
                existente.uso_directo = nodo.uso_directo
                existente.ruta = nodo.ruta

    return sorted(
        agregados.values(),
        key=lambda nodo: (nodo.nivel, nodo.ruta),
    )


def _buscar_material_demo(codigo: str) -> MaterialProductivo | None:
    datos = DEMO_MATERIALES.get(codigo)
    if datos is None:
        return None
    lotes = [
        LoteMaterial(lote=lote, stock=float(stock))
        for lote, stock in datos["lotes"]
    ]
    return MaterialProductivo(
        codigo=codigo,
        descripcion=datos["descripcion"],
        diametro=datos["diametro"],
        largo=datos["largo"],
        espesor=datos["espesor"],
        unidad=datos["unidad"],
        stock_total=sum(lote.stock for lote in lotes),
        lotes=lotes,
        fuente="demo",
    )


def _buscar_material_mysql(codigo: str) -> MaterialProductivo | None:
    inicio = perf_counter()
    logger.info("Material %s: conectando con la base productiva", codigo)

    with production_engine.connect() as conexion:
        maestra = conexion.execute(
            text(
                """
                SELECT
                    TRIM(`CODGO_`) AS codigo,
                    TRIM(COALESCE(`DESCR_`, '')) AS descripcion,
                    TRIM(COALESCE(CAST(`DIAMT_` AS CHAR), '')) AS diametro,
                    TRIM(COALESCE(CAST(`LARGO_` AS CHAR), '')) AS largo,
                    TRIM(COALESCE(CAST(`ESPES_` AS CHAR), '')) AS espesor,
                    TRIM(COALESCE(`UNDAD_`, '')) AS unidad
                FROM `mtprim01`
                WHERE UPPER(TRIM(`CODGO_`)) = :codigo
                LIMIT 1
                """
            ),
            {"codigo": codigo},
        ).mappings().first()

        if maestra is None:
            return None

        lotes_stock = conexion.execute(
            text(
                """
                SELECT
                    TRIM(COALESCE(`LOTE_`, '')) AS lote,
                    COALESCE(SUM(`CANT_`), 0) AS stock
                FROM `mtprim05`
                WHERE UPPER(TRIM(`CMAT_`)) = :codigo
                GROUP BY `LOTE_`
                ORDER BY `LOTE_`
                """
            ),
            {"codigo": codigo},
        ).mappings().all()

    lotes = [
        LoteMaterial(
            lote=str(fila["lote"] or ""),
            stock=float(fila["stock"] or 0),
        )
        for fila in lotes_stock
    ]
    logger.info(
        "Material %s: búsqueda completa en %.2f s (%s lotes)",
        codigo,
        perf_counter() - inicio,
        len(lotes),
    )
    return MaterialProductivo(
        codigo=str(maestra["codigo"] or ""),
        descripcion=str(maestra["descripcion"] or ""),
        diametro=str(maestra["diametro"] or ""),
        largo=str(maestra["largo"] or ""),
        espesor=str(maestra["espesor"] or ""),
        unidad=str(maestra["unidad"] or ""),
        stock_total=sum(lote.stock for lote in lotes),
        lotes=lotes,
        fuente="mysql",
    )


def _buscar_demo(codigo: str) -> PiezaProductiva | None:
    datos = DEMO_PIEZAS.get(codigo)
    if datos is None:
        return None
    operaciones = [
        OperacionPieza(
            operacion=operacion,
            titulo=titulo,
            stock=float(stock),
            proveedores=proveedores,
        )
        for operacion, titulo, stock, proveedores in datos["operaciones"]
    ]
    proveedores = sorted({
        operacion.proveedores
        for operacion in operaciones
        if operacion.proveedores
    })
    return PiezaProductiva(
        codigo=codigo,
        codigo_cliente=datos["codigo_cliente"],
        codigo_material=datos["codigo_material"],
        descripcion=datos["descripcion"],
        stock_terminado=float(datos["stock_terminado"]),
        stock_proceso_total=sum(item.stock for item in operaciones),
        proveedores_proceso=", ".join(proveedores),
        operaciones=operaciones,
        fuente="demo",
        tiene_operaciones_maestro=bool(operaciones),
        stock_material=48,
        lotes_material=[LoteMaterial(lote="DEMO-01", stock=48)],
        tipo_estructura=tipo_estructura_demo(codigo),
        descripcion_material=DEMO_MATERIALES.get(
            datos["codigo_material"], {}
        ).get("descripcion", ""),
        unidad_material=DEMO_MATERIALES.get(
            datos["codigo_material"], {}
        ).get("unidad", ""),
    )


def _buscar_mysql(codigo: str) -> PiezaProductiva | None:
    inicio = perf_counter()
    logger.info("Pieza %s: conectando con la base productiva", codigo)

    with production_engine.connect() as conexion:
        logger.info(
            "Pieza %s: conexión establecida en %.2f s",
            codigo,
            perf_counter() - inicio,
        )

        inicio_consulta = perf_counter()
        maestra = conexion.execute(
            text(
                """
                SELECT
                    TRIM(`GCOD_`) AS codigo,
                    TRIM(COALESCE(`CCOD_`, '')) AS codigo_cliente,
                    TRIM(COALESCE(`MATE_`, '')) AS codigo_material,
                    COALESCE(`CONS_`, 1) AS consumo_material,
                    TRIM(COALESCE(`UMCO_`, '')) AS unidad_consumo,
                    TRIM(COALESCE(`DESC_`, '')) AS descripcion,
                    COALESCE(`STOK_`, 0) AS stock_terminado
                FROM `produc01`
                WHERE `GCOD_` = :codigo
                LIMIT 1
                """
            ),
            {"codigo": codigo},
        ).mappings().first()

        logger.info(
            "Pieza %s: produc01 respondió en %.2f s",
            codigo,
            perf_counter() - inicio_consulta,
        )

        if maestra is None:
            return None

        codigo_material = str(maestra["codigo_material"] or "").strip()
        lotes_material = []
        material_maestro = None
        if codigo_material:
            inicio_consulta = perf_counter()
            material_maestro = conexion.execute(
                text(
                    """
                    SELECT
                        TRIM(COALESCE(`DESCR_`, '')) AS descripcion,
                        TRIM(COALESCE(`UNDAD_`, '')) AS unidad
                    FROM `mtprim01`
                    WHERE UPPER(TRIM(`CODGO_`)) = UPPER(:codigo_material)
                    LIMIT 1
                    """
                ),
                {"codigo_material": codigo_material},
            ).mappings().first()
            lotes_material = conexion.execute(
                text(
                    """
                    SELECT
                        TRIM(COALESCE(`LOTE_`, '')) AS lote,
                        COALESCE(SUM(`CANT_`), 0) AS stock
                    FROM `mtprim05`
                    WHERE `CMAT_` = :codigo_material
                    GROUP BY `LOTE_`
                    ORDER BY `LOTE_`
                    """
                ),
                {"codigo_material": codigo_material},
            ).mappings().all()

            logger.info(
                "Pieza %s: mtprim05 respondió en %.2f s (%s lotes)",
                codigo,
                perf_counter() - inicio_consulta,
                len(lotes_material),
            )

        inicio_consulta = perf_counter()
        operaciones_maestro = conexion.execute(
            text(
                """
                SELECT
                    TRIM(CAST(`OPER_` AS CHAR)) AS operacion,
                    TRIM(COALESCE(`CTITULO_`, '')) AS titulo
                FROM `produc21`
                WHERE `GCOD_` = :codigo
                ORDER BY
                    CAST(`OPER_` AS UNSIGNED),
                    `OPER_`
                """
            ),
            {"codigo": codigo},
        ).mappings().all()

        logger.info(
            "Pieza %s: produc21 respondió en %.2f s (%s operaciones)",
            codigo,
            perf_counter() - inicio_consulta,
            len(operaciones_maestro),
        )

        inicio_consulta = perf_counter()
        stocks_operaciones = conexion.execute(
            text(
                """
                SELECT
                    TRIM(CAST(`NPRO_` AS CHAR)) AS operacion,
                    COALESCE(SUM(`CANT_`), 0) AS stock,
                    GROUP_CONCAT(
                        DISTINCT NULLIF(
                            NULLIF(TRIM(CAST(`NPRV_` AS CHAR)), ''),
                            '0'
                        )
                        ORDER BY `NPRV_`
                        SEPARATOR ', '
                    ) AS proveedores
                FROM `produc05`
                WHERE `GCOD_` = :codigo
                GROUP BY `NPRO_`
                ORDER BY
                    CAST(`NPRO_` AS UNSIGNED),
                    `NPRO_`
                """
            ),
            {"codigo": codigo},
        ).mappings().all()

        pertenencia_estructura = conexion.execute(
            text(
                """
                SELECT
                    EXISTS(
                        SELECT 1
                        FROM `produc10`
                        WHERE TRIM(`VCOD_`) = :codigo
                    ) AS es_padre,
                    EXISTS(
                        SELECT 1
                        FROM `produc10`
                        WHERE TRIM(`GCOD_`) = :codigo
                    ) AS es_hijo
                """
            ),
            {"codigo": codigo},
        ).mappings().one()

        logger.info(
            "Pieza %s: produc05 respondió en %.2f s (%s stocks)",
            codigo,
            perf_counter() - inicio_consulta,
            len(stocks_operaciones),
        )

    stock_por_operacion = {
        str(fila["operacion"] or "").strip(): {
            "stock": float(fila["stock"] or 0),
            "proveedores": str(fila["proveedores"] or ""),
        }
        for fila in stocks_operaciones
    }

    operaciones = []
    operaciones_agregadas = set()

    for fila in operaciones_maestro:
        operacion = str(fila["operacion"] or "").strip()
        datos_stock = stock_por_operacion.get(
            operacion,
            {"stock": 0, "proveedores": ""},
        )
        operaciones.append(
            OperacionPieza(
                operacion=operacion,
                titulo=str(fila["titulo"] or ""),
                stock=datos_stock["stock"],
                proveedores=datos_stock["proveedores"],
            )
        )
        operaciones_agregadas.add(operacion)

    for operacion, datos_stock in stock_por_operacion.items():
        if operacion in operaciones_agregadas:
            continue
        operaciones.append(
            OperacionPieza(
                operacion=operacion,
                titulo="Operación sin descripción",
                stock=datos_stock["stock"],
                proveedores=datos_stock["proveedores"],
            )
        )

    proveedores = sorted({
        proveedor.strip()
        for fila in stocks_operaciones
        for proveedor in str(fila["proveedores"] or "").split(",")
        if proveedor.strip()
    })

    logger.info(
        "Pieza %s: búsqueda completa en %.2f s",
        codigo,
        perf_counter() - inicio,
    )

    return PiezaProductiva(
        codigo=str(maestra["codigo"]),
        codigo_cliente=str(maestra["codigo_cliente"] or ""),
        codigo_material=str(maestra["codigo_material"] or ""),
        descripcion=str(maestra["descripcion"] or ""),
        stock_terminado=float(maestra["stock_terminado"] or 0),
        stock_proceso_total=sum(
            float(fila["stock"] or 0)
            for fila in stocks_operaciones
        ),
        proveedores_proceso=", ".join(proveedores),
        operaciones=operaciones,
        fuente="mysql",
        tiene_operaciones_maestro=bool(operaciones_maestro),
        stock_material=sum(
            float(fila["stock"] or 0)
            for fila in lotes_material
        ),
        lotes_material=[
            LoteMaterial(
                lote=str(fila["lote"] or ""),
                stock=float(fila["stock"] or 0),
            )
            for fila in lotes_material
        ],
        tipo_estructura=resolver_tipo_estructura(
            bool(pertenencia_estructura["es_padre"]),
            bool(pertenencia_estructura["es_hijo"]),
        ),
        consumo_material=float(maestra["consumo_material"] or 1),
        unidad_consumo=str(maestra["unidad_consumo"] or "").strip() or "C/U",
        descripcion_material=(
            str(material_maestro["descripcion"] or "")
            if material_maestro else ""
        ),
        unidad_material=(
            str(material_maestro["unidad"] or "")
            if material_maestro else ""
        ),
    )
