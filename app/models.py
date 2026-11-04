from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Plantilla(Base):
    __tablename__ = "plantillas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    cliente: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    descripcion: Mapped[str] = mapped_column(String(255), default="")
    categoria: Mapped[str] = mapped_column(String(30), default="PIEZAS")
    tipo_inventario_codigo: Mapped[str] = mapped_column(
        String(50),
        default="PIEZAS_PROCESO",
        index=True,
    )
    tipo_conteo: Mapped[str] = mapped_column(String(30), default="GLOBAL")
    formato_impresion: Mapped[str] = mapped_column(
        String(40),
        default="FLUJO_HORIZONTAL",
    )
    controla_remitos: Mapped[bool] = mapped_column(Boolean, default=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )

    items: Mapped[list["PlantillaItem"]] = relationship(
        back_populates="plantilla",
        cascade="all, delete-orphan",
        order_by="PlantillaItem.id",
    )
    programaciones: Mapped[list["ProgramacionInventario"]] = relationship(
        back_populates="plantilla",
        cascade="all, delete-orphan",
    )


class FormatoImpresion(Base):
    __tablename__ = "formatos_impresion"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        unique=True,
        index=True,
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), default="")
    categoria: Mapped[str] = mapped_column(String(30), default="PIEZAS")
    editable: Mapped[bool] = mapped_column(Boolean, default=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    versiones: Mapped[list["FormatoVersion"]] = relationship(
        back_populates="formato",
        cascade="all, delete-orphan",
        order_by="FormatoVersion.numero",
    )


class FormatoVersion(Base):
    __tablename__ = "formato_versiones"
    __table_args__ = (
        UniqueConstraint("formato_id", "numero", name="uq_formato_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    formato_id: Mapped[int] = mapped_column(
        ForeignKey("formatos_impresion.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    nombre: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="Diseño sin nombre",
    )
    orientacion: Mapped[str] = mapped_column(
        String(20),
        default="HORIZONTAL",
    )
    margen_superior_mm: Mapped[float] = mapped_column(Float, default=8)
    margen_derecho_mm: Mapped[float] = mapped_column(Float, default=7)
    margen_inferior_mm: Mapped[float] = mapped_column(Float, default=8)
    margen_izquierdo_mm: Mapped[float] = mapped_column(Float, default=7)
    tamano_fuente_pt: Mapped[float] = mapped_column(Float, default=8)
    altura_fila_mm: Mapped[float] = mapped_column(Float, default=15)
    mostrar_firmas: Mapped[bool] = mapped_column(Boolean, default=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    formato: Mapped[FormatoImpresion] = relationship(back_populates="versiones")
    columnas: Mapped[list["FormatoColumna"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="FormatoColumna.orden",
    )


class FormatoColumna(Base):
    __tablename__ = "formato_columnas"
    __table_args__ = (
        UniqueConstraint(
            "version_id",
            "clave",
            name="uq_formato_columna",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("formato_versiones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clave: Mapped[str] = mapped_column(String(50), nullable=False)
    titulo: Mapped[str] = mapped_column(String(100), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    ancho_pct: Mapped[float] = mapped_column(Float, nullable=False, default=10)

    version: Mapped[FormatoVersion] = relationship(back_populates="columnas")


class PlantillaItem(Base):
    __tablename__ = "plantilla_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plantilla_id: Mapped[int] = mapped_column(
        ForeignKey("plantillas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    codigo: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    codigo_cliente: Mapped[str] = mapped_column(String(80), default="")
    codigo_material: Mapped[str] = mapped_column(String(80), default="")
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    ubicacion: Mapped[str] = mapped_column(String(80), default="")
    diametro: Mapped[str] = mapped_column(String(40), default="")
    largo: Mapped[str] = mapped_column(String(40), default="")
    espesor: Mapped[str] = mapped_column(String(40), default="")
    unidad: Mapped[str] = mapped_column(String(20), default="")
    stock_referencia: Mapped[float] = mapped_column(Float, default=0)
    contar_material: Mapped[bool] = mapped_column(Boolean, default=True)
    tipo_estructura: Mapped[str] = mapped_column(
        String(20),
        default="INDEPENDIENTE",
    )

    plantilla: Mapped[Plantilla] = relationship(back_populates="items")


class Inventario(Base):
    __tablename__ = "inventarios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    origen: Mapped[str] = mapped_column(
        String(20),
        default="PLANTILLA",
        index=True,
    )
    cliente: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    plantilla_id: Mapped[int | None] = mapped_column(
        ForeignKey("plantillas.id"),
        nullable=True,
    )
    programacion_id: Mapped[int | None] = mapped_column(
        ForeignKey("programaciones_inventario.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fecha_programada: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    responsable: Mapped[str] = mapped_column(String(120), nullable=False)
    colaboradores: Mapped[str] = mapped_column(String(1000), default="")
    ambito: Mapped[str] = mapped_column(
        String(20),
        default="INTERNO",
        index=True,
    )
    estado: Mapped[str] = mapped_column(
        String(30),
        default="En preparación",
        index=True,
    )
    categoria: Mapped[str] = mapped_column(String(30), default="PIEZAS")
    tipo_inventario_codigo: Mapped[str] = mapped_column(
        String(50),
        default="PIEZAS_PROCESO",
        index=True,
    )
    modalidad_conteo: Mapped[str] = mapped_column(
        String(20),
        default="ESTANDAR",
        index=True,
    )
    formato_impresion: Mapped[str] = mapped_column(
        String(40),
        default="FLUJO_HORIZONTAL",
    )
    formato_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("formato_versiones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    controla_remitos: Mapped[bool] = mapped_column(Boolean, default=False)
    ultimo_remito_ingreso: Mapped[str] = mapped_column(
        String(80),
        default="",
    )
    ultimo_remito_egreso: Mapped[str] = mapped_column(
        String(80),
        default="",
    )
    observaciones: Mapped[str] = mapped_column(Text, default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    stock_actualizado_en: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    stock_origen: Mapped[str] = mapped_column(
        String(30),
        default="BASE_PRODUCTIVA",
    )
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    items: Mapped[list["InventarioItem"]] = relationship(
        back_populates="inventario",
        cascade="all, delete-orphan",
        order_by="InventarioItem.id",
    )
    programacion: Mapped["ProgramacionInventario | None"] = relationship(
        back_populates="inventarios",
    )

    @property
    def mes_cierre(self) -> date:
        valor = getattr(self, "_mes_cierre_local", None)
        if valor is not None:
            return valor
        if self.id is not None:
            from app.local_closing_store import obtener_mes_inventario

            valor = obtener_mes_inventario(self.id)
            if valor is not None:
                self._mes_cierre_local = valor
        return valor or date(self.fecha.year, self.fecha.month, 1)

    @mes_cierre.setter
    def mes_cierre(self, valor: date | None) -> None:
        self._mes_cierre_local = (
            date(valor.year, valor.month, 1) if valor else None
        )


class ProgramacionInventario(Base):
    __tablename__ = "programaciones_inventario"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plantilla_id: Mapped[int] = mapped_column(
        ForeignKey("plantillas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha_proxima: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    frecuencia: Mapped[str] = mapped_column(String(20), default="UNA_VEZ")
    dia_mes: Mapped[int] = mapped_column(Integer, default=1)
    responsable: Mapped[str] = mapped_column(String(120), nullable=False)
    colaboradores: Mapped[str] = mapped_column(String(1000), default="")
    observaciones: Mapped[str] = mapped_column(Text, default="")
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    ultima_ejecucion: Mapped[date | None] = mapped_column(Date, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    plantilla: Mapped[Plantilla] = relationship(back_populates="programaciones")
    inventarios: Mapped[list[Inventario]] = relationship(
        back_populates="programacion",
        order_by="Inventario.id",
    )

    @property
    def mes_cierre_proximo(self) -> date:
        valor = getattr(self, "_mes_cierre_proximo_local", None)
        if valor is not None:
            return valor
        if self.id is not None:
            from app.local_closing_store import obtener_mes_programacion

            valor = obtener_mes_programacion(self.id)
            if valor is not None:
                self._mes_cierre_proximo_local = valor
        return valor or date(
            self.fecha_proxima.year,
            self.fecha_proxima.month,
            1,
        )

    @mes_cierre_proximo.setter
    def mes_cierre_proximo(self, valor: date | None) -> None:
        self._mes_cierre_proximo_local = (
            date(valor.year, valor.month, 1) if valor else None
        )


class CausaDiferencia(Base):
    __tablename__ = "causas_diferencia"

    codigo: Mapped[str] = mapped_column(String(50), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), default="")
    categoria: Mapped[str] = mapped_column(String(30), default="OTRA")
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class ConfiguracionSistema(Base):
    __tablename__ = "configuracion_sistema"

    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    valor: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), default="")
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )


class TipoInventario(Base):
    __tablename__ = "tipos_inventario"

    codigo: Mapped[str] = mapped_column(String(50), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), default="")
    motor: Mapped[str] = mapped_column(String(30), default="PIEZAS")
    modalidad: Mapped[str] = mapped_column(String(20), default="ESTANDAR")
    formato_impresion: Mapped[str] = mapped_column(
        String(40),
        default="FLUJO_HORIZONTAL",
    )
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )


class Sector(Base):
    __tablename__ = "sectores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
    )
    descripcion: Mapped[str] = mapped_column(String(255), default="")
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    personas: Mapped[list["Persona"]] = relationship(
        back_populates="sector",
    )


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("sectores.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    legajo: Mapped[str] = mapped_column(String(40), default="")
    contacto: Mapped[str] = mapped_column(String(120), default="")
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )

    sector: Mapped[Sector | None] = relationship(back_populates="personas")


class InventarioItem(Base):
    __tablename__ = "inventario_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    inventario_id: Mapped[int] = mapped_column(
        ForeignKey("inventarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    codigo: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    codigo_cliente: Mapped[str] = mapped_column(String(80), default="")
    codigo_material: Mapped[str] = mapped_column(String(80), default="")
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    ubicacion: Mapped[str] = mapped_column(String(80), default="")
    diametro: Mapped[str] = mapped_column(String(40), default="")
    largo: Mapped[str] = mapped_column(String(40), default="")
    espesor: Mapped[str] = mapped_column(String(40), default="")
    unidad: Mapped[str] = mapped_column(String(20), default="")
    lote: Mapped[str] = mapped_column(String(80), default="")
    codigo_padre: Mapped[str] = mapped_column(String(80), default="")
    nivel: Mapped[int] = mapped_column(Integer, default=0)
    uso: Mapped[float] = mapped_column(Float, default=1)
    ruta: Mapped[str] = mapped_column(String(2000), default="")
    tipo_estructura: Mapped[str] = mapped_column(
        String(20),
        default="INDEPENDIENTE",
        index=True,
    )
    etapa: Mapped[str] = mapped_column(
        String(30),
        default="TERMINADO",
        index=True,
    )
    operacion: Mapped[str] = mapped_column(String(50), default="")
    titulo_operacion: Mapped[str] = mapped_column(String(150), default="")
    proveedor: Mapped[str] = mapped_column(String(100), default="")
    stock_pendiente: Mapped[bool] = mapped_column(Boolean, default=False)
    stock_sistema: Mapped[float] = mapped_column(Float, default=0)
    stock_asignado: Mapped[float] = mapped_column(Float, default=0)
    conteo_fisico: Mapped[float | None] = mapped_column(Float, nullable=True)
    conteo_vacios: Mapped[float | None] = mapped_column(Float, nullable=True)
    conteo_llenos: Mapped[float | None] = mapped_column(Float, nullable=True)
    conteo_rotos: Mapped[float | None] = mapped_column(Float, nullable=True)
    contar_material: Mapped[bool] = mapped_column(Boolean, default=True)
    causa_diferencia_codigo: Mapped[str | None] = mapped_column(
        ForeignKey("causas_diferencia.codigo", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ajustado_sistema: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
    )
    ajustado_sistema_en: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    observaciones: Mapped[str] = mapped_column(Text, default="")

    inventario: Mapped[Inventario] = relationship(back_populates="items")


class Conciliacion(Base):
    __tablename__ = "conciliaciones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    inventario_inicial_id: Mapped[int] = mapped_column(Integer, nullable=False)
    inventario_final_id: Mapped[int] = mapped_column(Integer, nullable=False)
    inventario_inicial_codigo: Mapped[str] = mapped_column(String(30))
    inventario_final_codigo: Mapped[str] = mapped_column(String(30))
    fecha_inicial: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_final: Mapped[date] = mapped_column(Date, nullable=False)
    remito_ingreso_inicial: Mapped[str] = mapped_column(String(80), default="")
    remito_ingreso_final: Mapped[str] = mapped_column(String(80), default="")
    remito_egreso_inicial: Mapped[str] = mapped_column(String(80), default="")
    remito_egreso_final: Mapped[str] = mapped_column(String(80), default="")
    creada_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    items: Mapped[list["ConciliacionItem"]] = relationship(
        back_populates="conciliacion",
        cascade="all, delete-orphan",
        order_by="ConciliacionItem.id",
    )


class ConciliacionItem(Base):
    __tablename__ = "conciliacion_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conciliacion_id: Mapped[int] = mapped_column(
        ForeignKey("conciliaciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    codigo: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    descripcion: Mapped[str] = mapped_column(String(255), default="")
    stock_inicial: Mapped[float] = mapped_column(Float, default=0)
    detalle_inicial: Mapped[str] = mapped_column(Text, default="")
    ingresos: Mapped[float] = mapped_column(Float, default=0)
    egresos: Mapped[float] = mapped_column(Float, default=0)
    stock_final: Mapped[float] = mapped_column(Float, default=0)
    detalle_final: Mapped[str] = mapped_column(Text, default="")

    conciliacion: Mapped[Conciliacion] = relationship(back_populates="items")
