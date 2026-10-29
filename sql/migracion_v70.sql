USE inventarios_web;

SET @agregar_revision_conteo = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'inventarios'
              AND COLUMN_NAME = 'conteo_modificado_en'
        ),
        'SELECT 1',
        'ALTER TABLE inventarios ADD COLUMN conteo_modificado_en DATETIME(6) NULL AFTER stock_origen'
    )
);
PREPARE migracion_revision_conteo FROM @agregar_revision_conteo;
EXECUTE migracion_revision_conteo;
DEALLOCATE PREPARE migracion_revision_conteo;

CREATE TABLE IF NOT EXISTS conteo_cajas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_uid VARCHAR(64) NOT NULL,
    inventario_id INT NOT NULL,
    item_id INT NOT NULL,
    cantidad DOUBLE NOT NULL,
    observacion VARCHAR(255) NOT NULL DEFAULT '',
    dispositivo VARCHAR(80) NOT NULL DEFAULT '',
    capturado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_conteo_cajas_cliente_uid (cliente_uid),
    INDEX ix_conteo_cajas_inventario (inventario_id),
    INDEX ix_conteo_cajas_item (item_id),
    CONSTRAINT fk_conteo_cajas_inventario
        FOREIGN KEY (inventario_id)
        REFERENCES inventarios(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_conteo_cajas_item
        FOREIGN KEY (item_id)
        REFERENCES inventario_items(id)
        ON DELETE CASCADE
);
