CREATE TABLE IF NOT EXISTS inventario_reconteos (
    id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
    inventario_id INTEGER NOT NULL,
    numero INTEGER NOT NULL,
    tipo VARCHAR(20) NOT NULL DEFAULT 'PARCIAL',
    stock_referencia VARCHAR(20) NOT NULL DEFAULT 'ORIGINAL',
    estado VARCHAR(20) NOT NULL DEFAULT 'ABIERTO',
    responsable VARCHAR(120) NOT NULL DEFAULT '',
    observaciones TEXT NOT NULL,
    creado_en DATETIME NOT NULL,
    stock_capturado_en DATETIME NULL,
    cerrado_en DATETIME NULL,
    INDEX ix_reconteos_inventario (inventario_id),
    INDEX ix_reconteos_estado (estado),
    CONSTRAINT fk_reconteos_inventario FOREIGN KEY (inventario_id)
        REFERENCES inventarios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inventario_reconteo_items (
    id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
    reconteo_id INTEGER NOT NULL,
    inventario_item_id INTEGER NOT NULL,
    stock_sistema DOUBLE NOT NULL DEFAULT 0,
    conteo_fisico DOUBLE NULL,
    causa_diferencia_codigo VARCHAR(50) NULL,
    ajustado_sistema BOOLEAN NOT NULL DEFAULT 0,
    observaciones TEXT NOT NULL,
    guardado_en DATETIME NULL,
    INDEX ix_reconteo_items_reconteo (reconteo_id),
    INDEX ix_reconteo_items_original (inventario_item_id),
    CONSTRAINT fk_reconteo_items_reconteo FOREIGN KEY (reconteo_id)
        REFERENCES inventario_reconteos(id) ON DELETE CASCADE,
    CONSTRAINT fk_reconteo_items_original FOREIGN KEY (inventario_item_id)
        REFERENCES inventario_items(id) ON DELETE CASCADE
);
