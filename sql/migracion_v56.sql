USE inventarios_web;

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

ALTER TABLE inventarios
    ADD COLUMN formato_version_id INT NULL AFTER formato_impresion,
    ADD INDEX ix_inventarios_formato_version (formato_version_id),
    ADD CONSTRAINT fk_inventarios_formato_version
        FOREIGN KEY (formato_version_id)
        REFERENCES formato_versiones(id)
        ON DELETE SET NULL;
