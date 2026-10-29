-- Ejecutar sólo si preferís migrar manualmente desde MySQL Workbench.
-- El sistema también agrega estas columnas automáticamente al arrancar.

USE inventarios_web;

ALTER TABLE plantillas
    ADD COLUMN tipo_conteo VARCHAR(30) NOT NULL DEFAULT 'GLOBAL',
    ADD COLUMN categoria VARCHAR(30) NOT NULL DEFAULT 'PIEZAS',
    ADD COLUMN formato_impresion VARCHAR(40) NOT NULL DEFAULT 'FLUJO_HORIZONTAL',
    ADD COLUMN controla_remitos BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE inventarios
    ADD COLUMN categoria VARCHAR(30) NOT NULL DEFAULT 'PIEZAS',
    ADD COLUMN formato_impresion VARCHAR(40) NOT NULL DEFAULT 'FLUJO_HORIZONTAL',
    ADD COLUMN programacion_id INT NULL,
    ADD COLUMN fecha_programada DATE NULL,
    ADD COLUMN stock_actualizado_en DATETIME NULL,
    ADD COLUMN stock_origen VARCHAR(30) NOT NULL DEFAULT 'BASE_PRODUCTIVA',
    ADD COLUMN controla_remitos BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN ultimo_remito_ingreso VARCHAR(80) NOT NULL DEFAULT '',
    ADD COLUMN ultimo_remito_egreso VARCHAR(80) NOT NULL DEFAULT '',
    ADD COLUMN colaboradores VARCHAR(1000) NOT NULL DEFAULT '',
    ADD COLUMN ambito VARCHAR(20) NOT NULL DEFAULT 'INTERNO';

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

ALTER TABLE plantilla_items
    ADD COLUMN codigo_cliente VARCHAR(80) NOT NULL DEFAULT '',
    ADD COLUMN codigo_material VARCHAR(80) NOT NULL DEFAULT '',
    ADD COLUMN diametro VARCHAR(40) NOT NULL DEFAULT '',
    ADD COLUMN largo VARCHAR(40) NOT NULL DEFAULT '',
    ADD COLUMN espesor VARCHAR(40) NOT NULL DEFAULT '',
    ADD COLUMN unidad VARCHAR(20) NOT NULL DEFAULT '',
    ADD COLUMN contar_material BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE inventario_items
    ADD COLUMN codigo_cliente VARCHAR(80) NOT NULL DEFAULT '',
    ADD COLUMN codigo_material VARCHAR(80) NOT NULL DEFAULT '',
    ADD COLUMN diametro VARCHAR(40) NOT NULL DEFAULT '',
    ADD COLUMN largo VARCHAR(40) NOT NULL DEFAULT '',
    ADD COLUMN espesor VARCHAR(40) NOT NULL DEFAULT '',
    ADD COLUMN unidad VARCHAR(20) NOT NULL DEFAULT '',
    ADD COLUMN lote VARCHAR(80) NOT NULL DEFAULT '',
    ADD COLUMN codigo_padre VARCHAR(80) NOT NULL DEFAULT '',
    ADD COLUMN nivel INT NOT NULL DEFAULT 0,
    ADD COLUMN uso DOUBLE NOT NULL DEFAULT 1,
    ADD COLUMN ruta VARCHAR(2000) NOT NULL DEFAULT '',
    ADD COLUMN etapa VARCHAR(30) NOT NULL DEFAULT 'TERMINADO',
    ADD COLUMN operacion VARCHAR(50) NOT NULL DEFAULT '',
    ADD COLUMN titulo_operacion VARCHAR(150) NOT NULL DEFAULT '',
    ADD COLUMN proveedor VARCHAR(100) NOT NULL DEFAULT '',
    ADD COLUMN stock_pendiente BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN contar_material BOOLEAN NOT NULL DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS causas_diferencia (
    codigo VARCHAR(50) PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    descripcion VARCHAR(255) NOT NULL DEFAULT '',
    orden INT NOT NULL DEFAULT 0,
    activa BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT IGNORE INTO causas_diferencia
    (codigo, nombre, descripcion, orden, activa)
VALUES
    ('EN_INVESTIGACION', 'En investigación', 'La causa todavía no fue confirmada.', 10, TRUE),
    ('ERROR_CONTEO', 'Error de conteo', 'Reconteo, transcripción o identificación incorrecta.', 20, TRUE),
    ('MOVIMIENTO_NO_REGISTRADO', 'Movimiento no registrado', 'Ingreso, egreso o transferencia pendiente.', 30, TRUE),
    ('REMITO_PENDIENTE', 'Remito pendiente', 'Recepción o despacho todavía no procesado.', 40, TRUE),
    ('PRODUCCION_NO_REGISTRADA', 'Producción o consumo no registrado', 'Movimiento productivo pendiente.', 50, TRUE),
    ('SCRAP_NO_INFORMADO', 'Scrap o rechazo no informado', 'Baja o descarte pendiente.', 60, TRUE),
    ('UBICACION_INCORRECTA', 'Ubicación incorrecta', 'Artículo encontrado en otro sector.', 70, TRUE),
    ('UNIDAD_MEDICION', 'Diferencia de unidad o medición', 'Conversión o medición incorrecta.', 80, TRUE),
    ('ERROR_STOCK_SISTEMA', 'Error de stock del sistema', 'Saldo teórico inconsistente.', 90, TRUE),
    ('OTRA', 'Otra causa', 'Motivo no incluido en las categorías anteriores.', 100, TRUE);

ALTER TABLE inventario_items
    ADD COLUMN causa_diferencia_codigo VARCHAR(50) NULL,
    ADD COLUMN observaciones VARCHAR(1000) NOT NULL DEFAULT '',
    ADD INDEX ix_inventario_items_causa (causa_diferencia_codigo),
    ADD CONSTRAINT fk_inventario_items_causa
        FOREIGN KEY (causa_diferencia_codigo)
        REFERENCES causas_diferencia(codigo)
        ON DELETE SET NULL;
