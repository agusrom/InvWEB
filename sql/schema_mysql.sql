CREATE DATABASE IF NOT EXISTS inventarios_web
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE inventarios_web;

CREATE TABLE IF NOT EXISTS plantillas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    cliente VARCHAR(120) NOT NULL,
    descripcion VARCHAR(255) NOT NULL DEFAULT '',
    categoria VARCHAR(30) NOT NULL DEFAULT 'PIEZAS',
    tipo_inventario_codigo VARCHAR(50) NOT NULL DEFAULT 'PIEZAS_PROCESO',
    tipo_conteo VARCHAR(30) NOT NULL DEFAULT 'GLOBAL',
    formato_impresion VARCHAR(40) NOT NULL DEFAULT 'FLUJO_HORIZONTAL',
    controla_remitos BOOLEAN NOT NULL DEFAULT FALSE,
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    creada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_plantillas_cliente (cliente)
);

CREATE TABLE IF NOT EXISTS tipos_inventario (
    codigo VARCHAR(50) PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    descripcion VARCHAR(255) NOT NULL DEFAULT '',
    motor VARCHAR(30) NOT NULL DEFAULT 'PIEZAS',
    modalidad VARCHAR(20) NOT NULL DEFAULT 'ESTANDAR',
    formato_impresion VARCHAR(40) NOT NULL DEFAULT 'FLUJO_HORIZONTAL',
    orden INT NOT NULL DEFAULT 0,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_tipos_inventario_orden (orden)
);

INSERT IGNORE INTO tipos_inventario
    (codigo, nombre, descripcion, motor, modalidad, formato_impresion, orden)
VALUES
    ('PIEZAS_PROCESO', 'Piezas y proceso', 'Conteo estándar de material, proceso y terminado.', 'PIEZAS', 'ESTANDAR', 'FLUJO_HORIZONTAL', 10),
    ('MEDIOS', 'Medios', 'Conteo de medios vacíos, llenos y rotos.', 'PIEZAS', 'MEDIOS', 'MEDIOS', 20),
    ('MATERIA_PRIMA', 'Materia prima', 'Conteo de materiales y lotes.', 'MATERIA_PRIMA', 'ESTANDAR', 'MATERIA_PRIMA', 30),
    ('CICLICO', 'Cíclico', 'Explosión desde una pieza raíz.', 'CICLICO', 'ESTANDAR', 'CICLICO', 40);

CREATE TABLE IF NOT EXISTS sectores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL UNIQUE,
    descripcion VARCHAR(255) NOT NULL DEFAULT '',
    orden INT NOT NULL DEFAULT 0,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_sectores_orden (orden)
);

CREATE TABLE IF NOT EXISTS personas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    sector_id INT NULL,
    legajo VARCHAR(40) NOT NULL DEFAULT '',
    contacto VARCHAR(120) NOT NULL DEFAULT '',
    orden INT NOT NULL DEFAULT 0,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_personas_nombre (nombre),
    INDEX ix_personas_sector (sector_id),
    CONSTRAINT fk_personas_sector
        FOREIGN KEY (sector_id)
        REFERENCES sectores(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS plantilla_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plantilla_id INT NOT NULL,
    codigo VARCHAR(80) NOT NULL,
    codigo_cliente VARCHAR(80) NOT NULL DEFAULT '',
    codigo_material VARCHAR(80) NOT NULL DEFAULT '',
    descripcion VARCHAR(255) NOT NULL,
    ubicacion VARCHAR(80) NOT NULL DEFAULT '',
    diametro VARCHAR(40) NOT NULL DEFAULT '',
    largo VARCHAR(40) NOT NULL DEFAULT '',
    espesor VARCHAR(40) NOT NULL DEFAULT '',
    unidad VARCHAR(20) NOT NULL DEFAULT '',
    stock_referencia DOUBLE NOT NULL DEFAULT 0,
    contar_material BOOLEAN NOT NULL DEFAULT TRUE,
    tipo_estructura VARCHAR(20) NOT NULL DEFAULT 'INDEPENDIENTE',
    INDEX ix_plantilla_items_plantilla (plantilla_id),
    INDEX ix_plantilla_items_codigo (codigo),
    CONSTRAINT fk_plantilla_items_plantilla
        FOREIGN KEY (plantilla_id)
        REFERENCES plantillas(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS formatos_impresion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(40) NOT NULL UNIQUE,
    nombre VARCHAR(120) NOT NULL,
    descripcion VARCHAR(255) NOT NULL DEFAULT '',
    categoria VARCHAR(30) NOT NULL DEFAULT 'PIEZAS',
    editable BOOLEAN NOT NULL DEFAULT TRUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_formatos_impresion_codigo (codigo)
);

CREATE TABLE IF NOT EXISTS formato_versiones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    formato_id INT NOT NULL,
    numero INT NOT NULL DEFAULT 1,
    nombre VARCHAR(120) NOT NULL,
    orientacion VARCHAR(20) NOT NULL DEFAULT 'HORIZONTAL',
    margen_superior_mm DOUBLE NOT NULL DEFAULT 8,
    margen_derecho_mm DOUBLE NOT NULL DEFAULT 7,
    margen_inferior_mm DOUBLE NOT NULL DEFAULT 8,
    margen_izquierdo_mm DOUBLE NOT NULL DEFAULT 7,
    tamano_fuente_pt DOUBLE NOT NULL DEFAULT 8,
    altura_fila_mm DOUBLE NOT NULL DEFAULT 15,
    mostrar_firmas BOOLEAN NOT NULL DEFAULT TRUE,
    creada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_formato_versiones_formato (formato_id),
    UNIQUE KEY uq_formato_version (formato_id, numero),
    CONSTRAINT fk_formato_versiones_formato
        FOREIGN KEY (formato_id)
        REFERENCES formatos_impresion(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS formato_columnas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version_id INT NOT NULL,
    clave VARCHAR(50) NOT NULL,
    titulo VARCHAR(100) NOT NULL,
    orden INT NOT NULL DEFAULT 0,
    visible BOOLEAN NOT NULL DEFAULT TRUE,
    ancho_pct DOUBLE NOT NULL DEFAULT 10,
    INDEX ix_formato_columnas_version (version_id),
    UNIQUE KEY uq_formato_columna (version_id, clave),
    CONSTRAINT fk_formato_columnas_version
        FOREIGN KEY (version_id)
        REFERENCES formato_versiones(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inventarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    origen VARCHAR(20) NOT NULL DEFAULT 'PLANTILLA',
    cliente VARCHAR(120) NOT NULL,
    plantilla_id INT NULL,
    programacion_id INT NULL,
    fecha_programada DATE NULL,
    fecha DATE NOT NULL,
    responsable VARCHAR(120) NOT NULL,
    colaboradores VARCHAR(1000) NOT NULL DEFAULT '',
    ambito VARCHAR(20) NOT NULL DEFAULT 'INTERNO',
    estado VARCHAR(30) NOT NULL DEFAULT 'En preparación',
    categoria VARCHAR(30) NOT NULL DEFAULT 'PIEZAS',
    tipo_inventario_codigo VARCHAR(50) NOT NULL DEFAULT 'PIEZAS_PROCESO',
    modalidad_conteo VARCHAR(20) NOT NULL DEFAULT 'ESTANDAR',
    formato_impresion VARCHAR(40) NOT NULL DEFAULT 'FLUJO_HORIZONTAL',
    formato_version_id INT NULL,
    controla_remitos BOOLEAN NOT NULL DEFAULT FALSE,
    ultimo_remito_ingreso VARCHAR(80) NOT NULL DEFAULT '',
    ultimo_remito_egreso VARCHAR(80) NOT NULL DEFAULT '',
    observaciones TEXT NOT NULL,
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    stock_actualizado_en DATETIME NULL,
    stock_origen VARCHAR(30) NOT NULL DEFAULT 'BASE_PRODUCTIVA',
    cerrado_en DATETIME NULL,
    INDEX ix_inventarios_cliente (cliente),
    INDEX ix_inventarios_origen (origen),
    INDEX ix_inventarios_fecha (fecha),
    INDEX ix_inventarios_estado (estado),
    INDEX ix_inventarios_ambito (ambito),
    INDEX ix_inventarios_modalidad (modalidad_conteo),
    INDEX ix_inventarios_formato_version (formato_version_id),
    CONSTRAINT fk_inventarios_plantilla
        FOREIGN KEY (plantilla_id)
        REFERENCES plantillas(id),
    CONSTRAINT fk_inventarios_formato_version
        FOREIGN KEY (formato_version_id)
        REFERENCES formato_versiones(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS programaciones_inventario (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plantilla_id INT NOT NULL,
    fecha_proxima DATE NOT NULL,
    frecuencia VARCHAR(20) NOT NULL DEFAULT 'UNA_VEZ',
    dia_mes INT NOT NULL DEFAULT 1,
    responsable VARCHAR(120) NOT NULL,
    colaboradores VARCHAR(1000) NOT NULL DEFAULT '',
    observaciones TEXT NOT NULL,
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    ultima_ejecucion DATE NULL,
    creada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_programaciones_plantilla (plantilla_id),
    INDEX ix_programaciones_fecha (fecha_proxima),
    CONSTRAINT fk_programaciones_plantilla
        FOREIGN KEY (plantilla_id)
        REFERENCES plantillas(id)
        ON DELETE CASCADE
);

ALTER TABLE inventarios
    ADD CONSTRAINT fk_inventarios_programacion
        FOREIGN KEY (programacion_id)
        REFERENCES programaciones_inventario(id)
        ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS causas_diferencia (
    codigo VARCHAR(50) PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    descripcion VARCHAR(255) NOT NULL DEFAULT '',
    categoria VARCHAR(30) NOT NULL DEFAULT 'OTRA',
    orden INT NOT NULL DEFAULT 0,
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    INDEX ix_causas_diferencia_orden (orden)
);

INSERT IGNORE INTO causas_diferencia
    (codigo, nombre, descripcion, categoria, orden, activa)
VALUES
    ('EN_INVESTIGACION', 'En investigación', 'La causa todavía no fue confirmada.', 'OTRA', 10, TRUE),
    ('ERROR_CONTEO', 'Error de conteo', 'Reconteo, transcripción o identificación incorrecta.', 'CONTEO', 20, TRUE),
    ('MOVIMIENTO_NO_REGISTRADO', 'Movimiento no registrado', 'Ingreso, egreso o transferencia pendiente.', 'DOCUMENTACION', 30, TRUE),
    ('REMITO_PENDIENTE', 'Remito pendiente', 'Recepción o despacho todavía no procesado.', 'DOCUMENTACION', 40, TRUE),
    ('PRODUCCION_NO_REGISTRADA', 'Producción o consumo no registrado', 'Movimiento productivo pendiente.', 'PRODUCCION', 50, TRUE),
    ('SCRAP_NO_INFORMADO', 'Scrap o rechazo no informado', 'Baja o descarte pendiente.', 'PRODUCCION', 60, TRUE),
    ('UBICACION_INCORRECTA', 'Ubicación incorrecta', 'Artículo encontrado en otro sector.', 'UBICACION', 70, TRUE),
    ('UNIDAD_MEDICION', 'Diferencia de unidad o medición', 'Conversión o medición incorrecta.', 'CONTEO', 80, TRUE),
    ('ERROR_STOCK_SISTEMA', 'Error de stock del sistema', 'Saldo teórico inconsistente.', 'SISTEMA', 90, TRUE),
    ('OTRA', 'Otra causa', 'Motivo no incluido en las categorías anteriores.', 'OTRA', 100, TRUE);

CREATE TABLE IF NOT EXISTS configuracion_sistema (
    clave VARCHAR(80) PRIMARY KEY,
    valor VARCHAR(255) NOT NULL,
    descripcion VARCHAR(255) NOT NULL DEFAULT '',
    actualizada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);

INSERT IGNORE INTO configuracion_sistema
    (clave, valor, descripcion)
VALUES
    ('tolerancia_pct', '5.0', 'Desvío porcentual máximo para considerar correcto un renglón.'),
    ('objetivo_confiabilidad_pct', '90.0', 'Meta general de confiabilidad utilizada en reportes.'),
    ('alerta_cliente_pct', '85.0', 'Confiabilidad por debajo de la cual se genera una alerta.'),
    ('minimo_renglones_alerta', '3', 'Muestra mínima por cliente para emitir una alerta.');

CREATE TABLE IF NOT EXISTS inventario_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    inventario_id INT NOT NULL,
    codigo VARCHAR(80) NOT NULL,
    codigo_cliente VARCHAR(80) NOT NULL DEFAULT '',
    codigo_material VARCHAR(80) NOT NULL DEFAULT '',
    descripcion VARCHAR(255) NOT NULL,
    ubicacion VARCHAR(80) NOT NULL DEFAULT '',
    diametro VARCHAR(40) NOT NULL DEFAULT '',
    largo VARCHAR(40) NOT NULL DEFAULT '',
    espesor VARCHAR(40) NOT NULL DEFAULT '',
    unidad VARCHAR(20) NOT NULL DEFAULT '',
    lote VARCHAR(80) NOT NULL DEFAULT '',
    codigo_padre VARCHAR(80) NOT NULL DEFAULT '',
    nivel INT NOT NULL DEFAULT 0,
    uso DOUBLE NOT NULL DEFAULT 1,
    ruta VARCHAR(2000) NOT NULL DEFAULT '',
    tipo_estructura VARCHAR(20) NOT NULL DEFAULT 'INDEPENDIENTE',
    etapa VARCHAR(30) NOT NULL DEFAULT 'TERMINADO',
    operacion VARCHAR(50) NOT NULL DEFAULT '',
    titulo_operacion VARCHAR(150) NOT NULL DEFAULT '',
    proveedor VARCHAR(100) NOT NULL DEFAULT '',
    stock_pendiente BOOLEAN NOT NULL DEFAULT FALSE,
    stock_sistema DOUBLE NOT NULL DEFAULT 0,
    stock_asignado DOUBLE NOT NULL DEFAULT 0,
    conteo_fisico DOUBLE NULL,
    conteo_vacios DOUBLE NULL,
    conteo_llenos DOUBLE NULL,
    conteo_rotos DOUBLE NULL,
    contar_material BOOLEAN NOT NULL DEFAULT TRUE,
    causa_diferencia_codigo VARCHAR(50) NULL,
    ajustado_sistema BOOLEAN NOT NULL DEFAULT FALSE,
    ajustado_sistema_en DATETIME NULL,
    observaciones TEXT NOT NULL,
    INDEX ix_inventario_items_inventario (inventario_id),
    INDEX ix_inventario_items_codigo (codigo),
    INDEX ix_inventario_items_etapa (etapa),
    INDEX ix_inventario_items_tipo_estructura (tipo_estructura),
    INDEX ix_inventario_items_causa (causa_diferencia_codigo),
    INDEX ix_inventario_items_ajustado_sistema (ajustado_sistema),
    CONSTRAINT fk_inventario_items_inventario
        FOREIGN KEY (inventario_id)
        REFERENCES inventarios(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_inventario_items_causa
        FOREIGN KEY (causa_diferencia_codigo)
        REFERENCES causas_diferencia(codigo)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS conciliaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    inventario_inicial_id INT NOT NULL,
    inventario_final_id INT NOT NULL,
    inventario_inicial_codigo VARCHAR(30) NOT NULL,
    inventario_final_codigo VARCHAR(30) NOT NULL,
    fecha_inicial DATE NOT NULL,
    fecha_final DATE NOT NULL,
    remito_ingreso_inicial VARCHAR(80) NOT NULL DEFAULT '',
    remito_ingreso_final VARCHAR(80) NOT NULL DEFAULT '',
    remito_egreso_inicial VARCHAR(80) NOT NULL DEFAULT '',
    remito_egreso_final VARCHAR(80) NOT NULL DEFAULT '',
    creada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conciliacion_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conciliacion_id INT NOT NULL,
    codigo VARCHAR(80) NOT NULL,
    descripcion VARCHAR(255) NOT NULL DEFAULT '',
    stock_inicial DOUBLE NOT NULL DEFAULT 0,
    detalle_inicial TEXT NOT NULL,
    ingresos DOUBLE NOT NULL DEFAULT 0,
    egresos DOUBLE NOT NULL DEFAULT 0,
    stock_final DOUBLE NOT NULL DEFAULT 0,
    detalle_final TEXT NOT NULL,
    INDEX ix_conciliacion_items_conciliacion (conciliacion_id),
    INDEX ix_conciliacion_items_codigo (codigo),
    CONSTRAINT fk_conciliacion_items_conciliacion
        FOREIGN KEY (conciliacion_id)
        REFERENCES conciliaciones(id)
        ON DELETE CASCADE
);
