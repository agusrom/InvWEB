from datetime import date, datetime

from pydantic import BaseModel, Field


class PlantillaItemEntrada(BaseModel):
    codigo: str = Field(min_length=1, max_length=80)
    ubicacion: str = Field(default="", max_length=80)
    contar_material: bool = True


class PlantillaEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    cliente: str = Field(min_length=1, max_length=120)
    descripcion: str = Field(default="", max_length=255)
    categoria: str = Field(
        default="PIEZAS",
        pattern="^(PIEZAS|MATERIA_PRIMA)$",
    )
    tipo_inventario_codigo: str = Field(
        default="PIEZAS_PROCESO",
        min_length=1,
        max_length=50,
    )
    tipo_conteo: str = Field(pattern="^(GLOBAL|POR_OPERACION)$")
    formato_impresion: str = Field(
        default="FLUJO_HORIZONTAL",
        pattern="^(FLUJO_HORIZONTAL|DETALLE_ETAPAS|LISTADO_SIMPLE)$",
    )
    controla_remitos: bool = False
    activa: bool = True
    items: list[PlantillaItemEntrada]


class ArticuloInventarioEntrada(BaseModel):
    codigo: str = Field(min_length=1, max_length=80)
    tipo_articulo: str = Field(
        default="PIEZA",
        pattern="^(PIEZA|MATERIA_PRIMA)$",
    )
    contar_material: bool = True


class AgregarArticuloInventarioEntrada(ArticuloInventarioEntrada):
    tipo_conteo: str = Field(
        default="GLOBAL",
        pattern="^(GLOBAL|POR_OPERACION)$",
    )


class AgregarLoteMaterialEntrada(BaseModel):
    lote: str = Field(pattern=r"^\d{5}$")
    codigo_pieza: str = Field(default="", max_length=80)


class InventarioEntrada(BaseModel):
    modo: str = Field(
        default="PLANTILLA",
        pattern="^(PLANTILLA|CICLICO|MANUAL)$",
    )
    plantilla_id: int | None = None
    codigo_raiz: str = Field(default="", max_length=80)
    codigo_manual: str = Field(default="", max_length=80)
    tipo_articulo_manual: str = Field(
        default="PIEZA",
        pattern="^(PIEZA|MATERIA_PRIMA)$",
    )
    articulos_manual: list[ArticuloInventarioEntrada] = Field(
        default_factory=list,
    )
    contar_material: bool = True
    tipo_conteo: str = Field(
        default="GLOBAL",
        pattern="^(GLOBAL|POR_OPERACION)$",
    )
    controla_remitos: bool = False
    modalidad_conteo: str = Field(
        default="ESTANDAR",
        pattern="^(ESTANDAR|MEDIOS)$",
    )
    tipo_inventario_codigo: str = Field(
        default="",
        max_length=50,
    )
    fecha: date
    mes_cierre: date
    responsable: str = Field(min_length=1, max_length=120)
    colaboradores: str = Field(default="", max_length=1000)
    ambito: str = Field(
        default="INTERNO",
        pattern="^(INTERNO|CLIENTE)$",
    )
    observaciones: str = Field(default="", max_length=4000)


class ProgramacionEntrada(BaseModel):
    plantilla_id: int
    fecha_proxima: date
    mes_cierre_proximo: date
    frecuencia: str = Field(
        default="UNA_VEZ",
        pattern="^(UNA_VEZ|SEMANAL|MENSUAL)$",
    )
    responsable: str = Field(min_length=1, max_length=120)
    colaboradores: str = Field(default="", max_length=1000)
    observaciones: str = Field(default="", max_length=1000)


class ConteoItemEntrada(BaseModel):
    item_id: int
    conteo_fisico: float | None = Field(default=None, ge=0)
    conteo_vacios: float | None = Field(default=None, ge=0)
    conteo_llenos: float | None = Field(default=None, ge=0)
    conteo_rotos: float | None = Field(default=None, ge=0)
    causa_diferencia_codigo: str | None = Field(default=None, max_length=50)
    ajustado_sistema: bool = False
    observaciones: str = Field(default="", max_length=1000)


class ConteoEntrada(BaseModel):
    items: list[ConteoItemEntrada]
    revision_conteo: datetime | None = None
    ultimo_remito_ingreso: str = Field(default="", max_length=80)
    ultimo_remito_egreso: str = Field(default="", max_length=80)
    ambito: str | None = Field(
        default=None,
        pattern="^(INTERNO|CLIENTE)$",
    )
    observaciones: str | None = Field(default=None, max_length=4000)


class ReconteoCrearEntrada(BaseModel):
    tipo: str = Field(pattern="^(COMPLETO|PARCIAL)$")
    stock_referencia: str = Field(pattern="^(ORIGINAL|ACTUALIZADO)$")
    item_ids: list[int] = Field(min_length=1)
    responsable: str = Field(default="", max_length=120)
    observaciones: str = Field(default="", max_length=4000)


class ConteoCajaEntrada(BaseModel):
    cliente_uid: str = Field(min_length=8, max_length=64)
    item_id: int
    cantidad: int = Field(gt=0)
    observacion: str = Field(default="", max_length=255)
    dispositivo: str = Field(default="", max_length=80)
    capturado_en: datetime | None = None


class ConteoCajasEntrada(BaseModel):
    cajas: list[ConteoCajaEntrada] = Field(min_length=1, max_length=100)


class EliminarCajasMovilEntrada(BaseModel):
    caja_ids: list[int] = Field(min_length=1, max_length=100)


class ConteoMedioMovilEntrada(BaseModel):
    conteo_vacios: float = Field(ge=0)
    conteo_llenos: float = Field(ge=0)
    conteo_rotos: float = Field(ge=0)


class EliminarFilasInventarioEntrada(BaseModel):
    item_ids: list[int] = Field(min_length=1)
    ultimo_remito_ingreso: str = Field(default="", max_length=80)
    ultimo_remito_egreso: str = Field(default="", max_length=80)
    ambito: str | None = Field(
        default=None,
        pattern="^(INTERNO|CLIENTE)$",
    )
    observaciones: str | None = Field(default=None, max_length=4000)


class ReabrirInventarioEntrada(BaseModel):
    clave: str = Field(min_length=1, max_length=200)
    autorizado_por: str = Field(min_length=2, max_length=120)
    motivo: str = Field(min_length=3, max_length=500)


class CausaDiferenciaEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: str = Field(default="", max_length=255)
    categoria: str = Field(
        default="OTRA",
        pattern="^(PRODUCCION|DOCUMENTACION|CONTEO|UBICACION|SISTEMA|OTRA)$",
    )
    orden: int = Field(default=0, ge=0, le=9999)
    activa: bool = True


class ConfiguracionIndicadoresEntrada(BaseModel):
    tolerancia_pct: float = Field(ge=0, le=50)
    objetivo_confiabilidad_pct: float = Field(ge=0, le=100)
    alerta_cliente_pct: float = Field(ge=0, le=100)
    minimo_renglones_alerta: int = Field(ge=1, le=1000)


class FormatoColumnaEntrada(BaseModel):
    clave: str = Field(min_length=1, max_length=50)
    titulo: str = Field(min_length=1, max_length=100)
    visible: bool = True
    ancho_pct: float = Field(ge=2, le=80)
    tamano_fuente_pt: float | None = Field(default=None, ge=5, le=18)
    negrita: bool = False


class FormatoVersionEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    orientacion: str = Field(pattern="^(HORIZONTAL|VERTICAL)$")
    margen_superior_mm: float = Field(ge=3, le=30)
    margen_derecho_mm: float = Field(ge=3, le=30)
    margen_inferior_mm: float = Field(ge=3, le=30)
    margen_izquierdo_mm: float = Field(ge=3, le=30)
    tamano_fuente_pt: float = Field(ge=6, le=14)
    altura_fila_mm: float = Field(ge=6, le=30)
    mostrar_firmas: bool = True
    columnas: list[FormatoColumnaEntrada] = Field(min_length=2)


class TipoInventarioEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: str = Field(default="", max_length=255)
    motor: str = Field(pattern="^(PIEZAS|MATERIA_PRIMA|CICLICO)$")
    modalidad: str = Field(pattern="^(ESTANDAR|MEDIOS)$")
    formato_impresion: str = Field(min_length=1, max_length=40)
    orden: int = Field(default=0, ge=0, le=9999)
    activo: bool = True


class SectorEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: str = Field(default="", max_length=255)
    orden: int = Field(default=0, ge=0, le=9999)
    activo: bool = True


class PersonaEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    sector_id: int | None = None
    legajo: str = Field(default="", max_length=40)
    contacto: str = Field(default="", max_length=120)
    orden: int = Field(default=0, ge=0, le=9999)
    activo: bool = True


class InventarioDatosEntrada(BaseModel):
    ambito: str = Field(pattern="^(INTERNO|CLIENTE)$")
    mes_cierre: date
    observaciones: str = Field(default="", max_length=4000)


class ConciliacionEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    inventario_inicial_id: int
    inventario_final_id: int


class PreconciliacionCalculoEntrada(BaseModel):
    inventarios_iniciales: list[int] = Field(min_length=1, max_length=4)


class PreconciliacionExportacionEntrada(PreconciliacionCalculoEntrada):
    vista: str = Field(pattern="^(ANALISIS|CONCILIACION)$")
    analisis_id: str | None = Field(default=None, max_length=64)


class PreconciliacionGuardarEntrada(PreconciliacionCalculoEntrada):
    nombre: str = Field(min_length=1, max_length=150)


class PreconciliacionControlEntrada(BaseModel):
    cantidad_editada: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    verificado: bool = False
    observacion: str = Field(default="", max_length=1500)
    excluidos: list[int] = Field(default_factory=list, max_length=1000)


class PreconciliacionMovimientoLoteEntrada(PreconciliacionControlEntrada):
    clave: str = Field(min_length=1, max_length=300)


class PreconciliacionRemitoEntrada(BaseModel):
    inventarios_iniciales: list[int] = Field(min_length=1, max_length=4)
    recalcular: bool = False
    movimientos: list[PreconciliacionMovimientoLoteEntrada] = Field(
        min_length=1,
        max_length=2000,
    )


class PreconciliacionManualEntrada(BaseModel):
    tipo: str = Field(pattern="^(IN|OUT)$")
    fecha: date
    remito: str = Field(min_length=1, max_length=100)
    codigo: str = Field(min_length=1, max_length=80)
    cantidad: float = Field(gt=0, allow_inf_nan=False)
    observacion: str = Field(default="", max_length=1500)


class PreconciliacionScrapEntrada(BaseModel):
    inicial_id: int
    codigo: str = Field(min_length=1, max_length=80)
    cantidad: float = Field(ge=0, allow_inf_nan=False)


class PreconciliacionNotaEntrada(BaseModel):
    codigo: str = Field(min_length=1, max_length=80)
    causa: str = Field(default="", max_length=120)
    observacion: str = Field(default="", max_length=1500)
    estado: str = Field(
        default="PENDIENTE",
        pattern="^(PENDIENTE|RECONTAR|REVISAR_MOVIMIENTOS|AJUSTAR_SISTEMA|RESUELTO)$",
    )
    controles: dict[str, bool] = Field(default_factory=dict)


class ConciliacionItemEntrada(BaseModel):
    item_id: int
    ingresos: float = Field(default=0, ge=0)
    egresos: float = Field(default=0, ge=0)
    scrap: float = Field(default=0, ge=0)


class ConciliacionIngresoControlEntrada(BaseModel):
    movimiento_clave: str = Field(min_length=1, max_length=300)
    cantidad: float = Field(ge=0)
    verificado: bool = False
    observacion: str = Field(default="", max_length=1000)


class ConciliacionIngresoManualEntrada(BaseModel):
    item_id: int
    codigo_material: str = Field(min_length=1, max_length=80)
    remito: str = Field(default="MANUAL", min_length=1, max_length=80)
    fecha: date
    cantidad: float = Field(gt=0)
    observacion: str = Field(default="", max_length=1000)


class ConciliacionEgresoControlEntrada(BaseModel):
    movimiento_clave: str = Field(min_length=1, max_length=300)
    cantidad: float = Field(ge=0)
    verificado: bool = False
    observacion: str = Field(default="", max_length=1000)


class ConciliacionEgresoManualEntrada(BaseModel):
    item_id: int
    remito: str = Field(default="MANUAL", min_length=1, max_length=80)
    fecha: date
    cantidad: float = Field(gt=0)
    observacion: str = Field(default="", max_length=1000)


class ConciliacionMovimientosEntrada(BaseModel):
    items: list[ConciliacionItemEntrada]
    controles_ingreso: list[ConciliacionIngresoControlEntrada] = Field(
        default_factory=list,
    )
    controles_egreso: list[ConciliacionEgresoControlEntrada] = Field(
        default_factory=list,
    )
