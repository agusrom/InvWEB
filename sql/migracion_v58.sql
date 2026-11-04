USE inventarios_web;

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
    ('PIEZAS_PROCESO', 'Piezas y proceso',
     'Conteo estándar de material, proceso y terminado.',
     'PIEZAS', 'ESTANDAR', 'FLUJO_HORIZONTAL', 10),
    ('MEDIOS', 'Medios',
     'Conteo de medios vacíos, llenos y rotos.',
     'PIEZAS', 'MEDIOS', 'MEDIOS', 20),
    ('MATERIA_PRIMA', 'Materia prima',
     'Conteo de materiales y lotes.',
     'MATERIA_PRIMA', 'ESTANDAR', 'MATERIA_PRIMA', 30),
    ('CICLICO', 'Cíclico',
     'Explosión desde una pieza raíz.',
     'CICLICO', 'ESTANDAR', 'CICLICO', 40);

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

ALTER TABLE plantillas
    ADD COLUMN tipo_inventario_codigo VARCHAR(50)
        NOT NULL DEFAULT 'PIEZAS_PROCESO';

ALTER TABLE inventarios
    ADD COLUMN tipo_inventario_codigo VARCHAR(50)
        NOT NULL DEFAULT 'PIEZAS_PROCESO';

UPDATE plantillas
SET tipo_inventario_codigo = CASE
    WHEN categoria = 'MATERIA_PRIMA' THEN 'MATERIA_PRIMA'
    ELSE 'PIEZAS_PROCESO'
END;

UPDATE inventarios
SET tipo_inventario_codigo = CASE
    WHEN categoria = 'CICLICO' THEN 'CICLICO'
    WHEN categoria = 'MATERIA_PRIMA' THEN 'MATERIA_PRIMA'
    WHEN modalidad_conteo = 'MEDIOS' THEN 'MEDIOS'
    ELSE 'PIEZAS_PROCESO'
END;

CREATE INDEX ix_plantillas_tipo_inventario
    ON plantillas (tipo_inventario_codigo);

CREATE INDEX ix_inventarios_tipo_inventario
    ON inventarios (tipo_inventario_codigo);
